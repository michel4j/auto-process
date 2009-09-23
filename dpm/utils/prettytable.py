#!/usr/bin/env python
#
# Copyright (c) 2009, Luke Maurits <luke@maurits.id.au>
# All rights reserved.
# With contributions from:
#  * Chris Clark
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# * The name of the author may not be used to endorse or promote products
#   derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

__version__ = "0.6"

import cgi
import copy
import cPickle
import random
import sys

# hrule styles
FRAME = 0
ALL   = 1
NONE  = 2

# Table styles
DEFAULT = 10
MSWORD_FRIENDLY = 11
PLAIN_COLUMNS = 12
RANDOM = 20

def cache_clearing(method):
    def wrapper(self, *args, **kwargs):
        method(self, *args, **kwargs)
        self._cache = {}
        self.html_cache = {}
    return wrapper

class PrettyTable(object):

    def __init__(self, field_names=None, **kwargs):

        """Return a new PrettyTable instance

        Arguments:

        field_names - list or tuple of field names
        fields - list or tuple of field names to include in displays
        caching - boolean value to turn string caching on/off
        start - index of first data row to include in output
        end - index of last data row to include in output PLUS ONE (list slice style)
        fields - names of fields (columns) to include
        header - print a header showing field names (True or False)
        border - print a border around the table (True or False)
        hrules - controls printing of horizontal rules after rows.  Allowed values: FRAME, ALL, NONE
        padding_width - number of spaces on either side of column data (only used if left and right paddings are None)
        left_padding_width - number of spaces on left hand side of column data
        right_padding_width - number of spaces on right hand side of column data
        vertical_char - single character string used to draw vertical lines
        horizontal_char - single character string used to draw horizontal lines
        junction_char - single character string used to draw line junctions
        sortby - name of field to sort rows by
        reversesort - True or False to sort in descending or ascending order"""

        # Data
        self._field_names = []
        self._align = {}
        if field_names:
            self.field_names = field_names
        else:
            self._widths = []
        self._rows = []
        self._cache = {}
        self.html_cache = {}

        # Options
        self._options = "start end fields header border sortby reversesort attributes format hrules caching".split()
        self._options.extend("padding_width left_padding_width right_padding_width".split())
        self._options.extend("vertical_char horizontal_char junction_char".split())
        for option in self._options:
            if option in kwargs:
                self._validate_option(option, kwargs[option])
            else:
                kwargs[option] = None

        self._caching = kwargs["caching"] or True

        self._start = kwargs["start"] or 0
        self._end = kwargs["end"] or None
        self._fields = kwargs["fields"] or None

        self._header = kwargs["header"] or True
        self._border = kwargs["border"] or True
        self._hrules = kwargs["hrules"] or FRAME

        self._sortby = kwargs["sortby"] or None
        self._reversesort = kwargs["reversesort"] or False

        self._padding_width = kwargs["padding_width"] or 1
        self._left_padding_width = kwargs["left_padding_width"] or None
        self._right_padding_width = kwargs["right_padding_width"] or None

        self._vertical_char = kwargs["vertical_char"] or "|"
        self._horizontal_char = kwargs["horizontal_char"] or "-"
        self._junction_char = kwargs["junction_char"] or "+"
        
        self._format = kwargs["format"] or False
        self._attributes = kwargs["attributes"] or {}
   
    def __getattr__(self, name):

        if name == "rowcount":
            return len(self._rows)
        elif name == "colcount":
            return len(self._field_names)
        else:
            raise AttributeError, name
 
    def __getslice__(self, i, j):

        """Return a new PrettyTable whose data rows are a slice of this one's

        Arguments:

        i - beginning slice index
        j - ending slice index"""

        newtable = copy.deepcopy(self)
        newtable.rows = self._rows[i:j]
        return newtable

    def __str__(self):

        return self.get_string()

    ##############################
    # ATTRIBUTE VALIDATORS       #
    ##############################

    # The method _validate_option is all that should be used elsewhere in the code base to validate options.
    # It will call the appropriate validation method for that option.  The individual validation methods should
    # never need to be called directly (although nothing bad will happen if they *are*).
    # Validation happens in TWO places.
    # Firstly, in the property setters defined in the ATTRIBUTE MANAGMENT section.
    # Secondly, in the _get_options method, where keyword arguments are mixed with persistent settings

    def _validate_option(self, option, val):
        if option in ("start", "end", "padding_width", "left_padding_width", "right_padding_width", "format"):
            self._validate_nonnegative_int(option, val)
        elif option in ("sortby"):
            self._validate_field_name(option, val)
        elif option in ("hrules"):
            self._validate_hrules(option, val)
        elif option in ("fields"):
            self._validate_all_field_names(option, val)
        elif option in ("header", "border", "caching", "reversesort"):
            self._validate_true_or_false(option, val)
        elif option in ("vertical_char", "horizontal_char", "junction_char"):
            self._validate_single_char(option, val)
        elif option in ("attributes"):
            self._validate_attributes(option, val)
        else:
            raise Exception("Unrecognised option: %s!" % option)

    def _validate_align(self, val):
        try:
            assert val in ["l","c","r"]
        except AssertionError:
            raise Exception("Alignment %s is invalid, use l, c or r!" % val)

    def _validate_nonnegative_int(self, name, val):
        try:
            assert int(val) >= 0
        except AssertionError:
            raise Exception("Invalid value for %s: %s!" % (name, unicode(val)))

    def _validate_true_or_false(self, name, val):
        try:
            assert val in (True, False)
        except AssertionError:
            raise Exception("Invalid value for %s!  Must be True or False." % name)

    def _validate_hrules(self, name, val):
        try:
            assert val in (ALL, FRAME, NONE)
        except AssertionError:
            raise Exception("Invalid value for %s!  Must be ALL, FRAME or NONE." % name)

    def _validate_field_name(self, name, val):
        try:
            assert val in self._field_names
        except AssertionError:
            raise Exception("Invalid field name: %s!" % val)

    def _validate_all_field_names(self, name, val):
        try:
            for x in val:
                self._validate_field_name(name, x)
        except AssertionError:
            raise Exception("fields must be a sequence of field names!")

    def _validate_single_char(self, name, val):
        try:
            assert len(unicode(val)) == 1
        except AssertionError:
            raise Exception("Invalid value for %s!  Must be a string of length 1." % name)

    def _validate_attributes(self, name, val):
        try:
            assert isinstance(val, dict)
        except AssertionError:
            raise Exception("attributes must be a dictionary of name/value pairs!")

    ##############################
    # ATTRIBUTE MANAGEMENT       #
    ##############################

    def _get_field_names(self):
        return self._field_names
        """The names of the fields

        Arguments:

        fields - list or tuple of field names"""
    #@cache_clearing
    def _set_field_names(self, val):
        # We *may* need to change the widths if this isn't the first time
        # setting the field names.  This could certainly be done more
        # efficiently.
        if self._field_names:
            self._recompute_widths()
        else:
            self._widths = [len(field) for field in val]
        self._field_names = val
        self.align = "c"
    field_names = property(_get_field_names, _set_field_names)

    def _get_align(self):
        return self._align
    #@cache_clearing
    def _set_align(self, val):
        self._validate_align(val)
        for field in self._field_names:
            self._align[field] = val
    align = property(_get_align, _set_align)

    def _get_start(self):
        """Start index of the range of rows to print

        Arguments:

        start - index of first data row to include in output"""
        return self._start
    def _set_start(self, val):
        self._validate_option("start", val)
        self._start = val
    start = property(_get_start, _set_start)

    def _get_end(self):
        """End index of the range of rows to print

        Arguments:

        end - index of last data row to include in output PLUS ONE (list slice style)"""
        return self._end
    def _set_end(self, val):
        self._validate_option("end", val)
        self._end = val
    end = property(_get_end, _set_end)

    def _get_sortby(self):
        """Name of field by which to sort rows

        Arguments:

        sortby - field name to sort by"""
        return self._sortby
    def _set_sortby(self, val):
        self._validate_option("sortby", val)
        self._sortby = val
    sortby = property(_get_sortby, _set_sortby)

    def _get_reversesort(self):
        """Controls direction of sorting (ascending vs descending)

        Arguments:

        reveresort - set to True to sort by descending order, or False to sort by ascending order"""
        return self._reversesort
    def _set_reversesort(self, val):
        self._validate_option("reversesort", val)
        self._reversesort = val
    reversesort = property(_get_reversesort, _set_reversesort)

    def _get_header(self):
        """Controls printing of table header with field names

        Arguments:

        header - print a header showing field names (True or False)"""
        return self._header
    def _set_header(self, val):
        self._validate_option("header", val)
        self._header = val
    header = property(_get_header, _set_header)

    def _get_border(self):
        """Controls printing of border around table

        Arguments:

        border - print a border around the table (True or False)"""
        return self._border
    def _set_border(self, val):
        self._validate_option("border", val)
        self._border = val
    border = property(_get_border, _set_border)

    def _get_hrules(self):
        """Controls printing of horizontal rules after rows

        Arguments:

        hrules - horizontal rules style.  Allowed values: FRAME, ALL, NONE"""
        return self._hrules
    def _set_hrules(self, val):
        self._validate_option("hrules", val)
        self._hrules = val
    hrules = property(_get_hrules, _set_hrules)

    def _get_padding_width(self):
        """The number of empty spaces between a column's edge and its content

        Arguments:

        padding_width - number of spaces, must be a positive integer"""
        return self._padding_width
    def _set_padding_width(self, val):
        self._validate_option("padding_width", val)
        self._padding_width = val
    padding_width = property(_get_padding_width, _set_padding_width)

    def _get_left_padding_width(self):
        """The number of empty spaces between a column's left edge and its content

        Arguments:

        left_padding - number of spaces, must be a positive integer"""
        return self._left_padding_width
    def _set_left_padding_width(self, val):
        self._validate_option("left_padding_width", val)
        self._left_padding_width = val
    left_padding_width = property(_get_left_padding_width, _set_left_padding_width)

    def _get_right_padding_width(self):
        """The number of empty spaces between a column's right edge and its content

        Arguments:

        right_padding - number of spaces, must be a positive integer"""
        return self._right_padding_width
    def _set_right_padding_width(self, val):
        self._validate_option("right_padding_width", val)
        self._right_padding_width = val
    right_padding_width = property(_get_right_padding_width, _set_right_padding_width)

    def _get_vertical_char(self):
        """The charcter used when printing table borders to draw vertical lines

        Arguments:

        vertical_char - single character string used to draw vertical lines"""
        return self._vertical_char
    def _set_vertical_char(self, val):
        self._validate_option("vertical_char", val)
        self._vertical_char = val
    vertical_char = property(_get_vertical_char, _set_vertical_char)

    def _get_horizontal_char(self):
        """The charcter used when printing table borders to draw horizontal lines

        Arguments:

        horizontal_char - single character string used to draw horizontal lines"""
        return self._horizontal_char
    def _set_horizontal_char(self, val):
        self._validate_option("horizontal_char", val)
        self._horizontal_char = val
    horizontal_char = property(_get_horizontal_char, _set_horizontal_char)

    def _get_junction_char(self):
        """The charcter used when printing table borders to draw line junctions

        Arguments:

        junction_char - single character string used to draw line junctions"""
        return self._junction_char
    def _set_junction_char(self, val):
        self._validate_option("vertical_char", val)
        self._junction_char = val
    junction_char = property(_get_junction_char, _set_junction_char)

    def _get_format(self):
        """Controls whether or not HTML tables are formatted to match styling options

        Arguments:

        format - True or False"""
        return self._format
    def _set_format(self, val):
        self._validate_option("format", val)
        self._format = val
    format = property(_get_format, _set_format)

    def _get_attributes(self):
        """A dictionary of HTML attribute name/value pairs to be included in the <table> tag when printing HTML

        Arguments:

        attributes - dictionary of attributes"""
        return self._attributes
    def _set_attributes(self, val):
        self.validate_option("attributes", val)
        self._attributes = val
    attributes = property(_get_attributes, _set_attributes)

    ##############################
    # OPTION MIXER               #
    ##############################

    def _get_options(self, kwargs):

        options = {}
        for option in self._options:
            if option in kwargs:
                self._validate_option(option, kwargs[option])
                options[option] = kwargs[option]
            else:
                options[option] = getattr(self, "_"+option)
        return options

    ##############################
    # PRESET STYLE LOGIC         #
    ##############################

    def set_style(self, style):

        if style == DEFAULT:
            self._set_default_style()
        elif style == MSWORD_FRIENDLY:
            self._set_msword_style()
        elif style == PLAIN_COLUMNS:
            self._set_columns_style()
        elif style == RANDOM:
            self._set_random_style()
        else:
            raise Exception("Invalid pre-set style!")

    def _set_default_style(self):

        self.header = True
        self.border = True
        self.hrules = FRAME
        self.padding_width = 1
        self.left_padding_width = 1
        self.right_padding_width = 1
        self.vertical_char = "|"
        self.horizontal_char = "-"
        self.junction_char = "+"

    def _set_msword_style(self):

        self.header = True
        self.border = True
        self.hrules = NONE
        self.padding_width = 1
        self.left_padding_width = 1
        self.right_padding_width = 1
        self.vertical_char = "|"

    def _set_columns_style(self):

        self.header = True
        self.border = False
        self.padding_width = 1
        self.left_padding_width = 0
        self.right_padding_width = 8

    def _set_random_style(self):

        # Just for fun!
        self.header = random.choice((True, False))
        self.border = random.choice((True, False))
        self.hrules = random.choice((ALL, FRAME, NONE))
        self.left_padding_width = random.randint(0,5)
        self.right_padding_width = random.randint(0,5)
        self.vertical_char = random.choice("~!@#$%^&*()_+|-=\{}[];':\",./;<>?")
        self.horizontal_char = random.choice("~!@#$%^&*()_+|-=\{}[];':\",./;<>?")
        self.junction_char = random.choice("~!@#$%^&*()_+|-=\{}[];':\",./;<>?")

    ##############################
    # DATA INPUT METHODS         #
    ##############################

    #@cache_clearing
    def add_row(self, row):

        """Add a row to the table

        Arguments:

        row - row of data, should be a list with as many elements as the table
        has fields"""

        if len(row) != len(self._field_names):
            raise Exception("Row has incorrect number of values, (actual) %d!=%d (expected)" %(len(row),len(self._field_names)))
        self._rows.append(row)
        for i in range(0,len(row)):
            if len(unicode(row[i])) > self._widths[i]:
                self._widths[i] = len(unicode(row[i]))

    #@cache_clearing
    def del_row(self, row_index):

        """Delete a row to the table

        Arguments:

        row_index - The index of the row you want to delete.  Indexing starts at 0."""

        if row_index > len(self._rows)-1:
            raise Exception("Cant delete row at index %d, table only has %d rows!" % (row_index, len(self._rows)))
        del self._rows[row_index]
        self._recompute_widths()

    #@cache_clearing
    def add_column(self, fieldname, column, align="c"):

        """Add a column to the table.

        Arguments:

        fieldname - name of the field to contain the new column of data
        column - column of data, should be a list with as many elements as the
        table has rows
        align - desired alignment for this column - "l" for left, "c" for centre and "r" for right"""

        if len(self._rows) in (0, len(column)):
            self._validate_align(align)
            self._field_names.append(fieldname)
            self._widths.append(len(fieldname))
            self._align[fieldname] = align
            for i in range(0, len(column)):
                if len(self._rows) < i+1:
                    self._rows.append([])
                self._rows[i].append(column[i])
                if len(unicode(column[i])) > self._widths[-1]:
                    self._widths[-1] = len(unicode(column[i]))
        else:
            raise Exception("Column length %d does not match number of rows %d!" % (len(column), len(self._rows)))

    #@cache_clearing
    def clear_rows(self):

        """Delete all rows from the table but keep the current field names"""

        self._rows = []
        self._widths = [len(unicode(field_name)) for field_name in self._field_names]

    #@cache_clearing
    def clear(self):

        """Delete all rows and field names from the table, maintaining nothing but styling options"""

        self._rows = []
        self._field_names = []
        self._widths = []

    ##############################
    # MISC PUBLIC METHODS        #
    ##############################

    def copy(self):
        return copy.deepcopy(self)

    ##############################
    # MISC PRIVATE METHODS       #
    ##############################

    def _recompute_widths(self):
        self._widths = [len(field) for field in self._field_names]
        for row in self._rows:
            for i in range(0,len(row)):
                if len(unicode(row[i])) > self._widths[i]:
                    self._widths[i] = len(unicode(row[i]))

    def _get_padding_widths(self, options):

        if options["left_padding_width"] is not None:
            lpad = options["left_padding_width"]
        else:
            lpad = options["padding_width"]
        if options["right_padding_width"] is not None:
            rpad = options["right_padding_width"]
        else:
            rpad = options["padding_width"]
        return lpad, rpad

    def _get_sorted_rows(self, options):
        # Sort rows using the "Decorate, Sort, Undecorate" (DSU) paradigm
        rows = copy.deepcopy(self._rows[options["start"]:options["end"]])
        sortindex = self._field_names.index(options["sortby"])
        # Decorate
        rows = [[row[sortindex]]+row for row in rows]
        # Sort
        rows.sort(reverse=options["reversesort"])
        # Undecorate
        rows = [row[1:] for row in rows]
        return rows

    ##############################
    # ASCII PRINT/STRING METHODS #
    ##############################

    def printt(self, **kwargs):

        """Print table in current state to stdout.

        Arguments:

        start - index of first data row to include in output
        end - index of last data row to include in output PLUS ONE (list slice style)
        fields - names of fields (columns) to include
        header - print a header showing field names (True or False)
        border - print a border around the table (True or False)
        hrules - controls printing of horizontal rules after rows.  Allowed values: FRAME, ALL, NONE
        padding_width - number of spaces on either side of column data (only used if left and right paddings are None)
        left_padding_width - number of spaces on left hand side of column data
        right_padding_width - number of spaces on right hand side of column data
        vertical_char - single character string used to draw vertical lines
        horizontal_char - single character string used to draw horizontal lines
        junction_char - single character string used to draw line junctions
        sortby - name of field to sort rows by
        reversesort - True or False to sort in descending or ascending order"""

        print self.get_string(**kwargs)

    def get_string(self, **kwargs):

        """Return string representation of table in current state.

        Arguments:

        start - index of first data row to include in output
        end - index of last data row to include in output PLUS ONE (list slice style)
        fields - names of fields (columns) to include
        header - print a header showing field names (True or False)
        border - print a border around the table (True or False)
        hrules - controls printing of horizontal rules after rows.  Allowed values: FRAME, ALL, NONE
        padding_width - number of spaces on either side of column data (only used if left and right paddings are None)
        left_padding_width - number of spaces on left hand side of column data
        right_padding_width - number of spaces on right hand side of column data
        vertical_char - single character string used to draw vertical lines
        horizontal_char - single character string used to draw horizontal lines
        junction_char - single character string used to draw line junctions
        sortby - name of field to sort rows by
        reversesort - True or False to sort in descending or ascending order"""

        options = self._get_options(kwargs)

        if self._caching:
            key = cPickle.dumps(options)
            if key in self._cache:
                return self._cache[key]

        bits = []
        if not self._field_names:
            return ""
        if not options["header"]:
            # Recalculate widths - avoids tables with long field names but narrow data looking odd
            old_widths = self._widths[:]
            self._widths = [0]*len(self._field_names)
            for row in self._rows:
                for i in range(0,len(row)):
                    if len(unicode(row[i])) > self._widths[i]:
                        self._widths[i] = len(unicode(row[i]))
        if options["header"]:
            bits.append(self._stringify_header(options))
        elif options["border"] and options["hrules"] != NONE:
            bits.append(self._stringify_hrule(options))
        if options["sortby"]:
            rows = self._get_sorted_rows(options)
        else:
            rows = self._rows[options["start"]:options["end"]]
        for row in rows:
            bits.append(self._stringify_row(row, options))
        if options["border"] and not options["hrules"]:
            bits.append(self._stringify_hrule(options))
        string = "\n".join(bits)

        if self._caching:
            self._cache[key] = string

        if not options["header"]:
            # Restore previous widths
            self._widths = old_widths
            for row in self._rows:
                for i in range(0,len(row)):
                    if len(unicode(row[i])) > self._widths[i]:
                        self._widths[i] = len(unicode(row[i]))

        return string

    def _stringify_hrule(self, options):

        if not options["border"]:
            return ""
        lpad, rpad = self._get_padding_widths(options)
        bits = [options["junction_char"]]
        for field, width in zip(self._field_names, self._widths):
            if options["fields"] and field not in options["fields"]:
                continue
            bits.append((width+lpad+rpad)*options["horizontal_char"])
            bits.append(options["junction_char"])
        return "".join(bits)

    def _stringify_header(self, options):

        bits = []
        lpad, rpad = self._get_padding_widths(options)
        if options["border"]:
            if options["hrules"] != NONE:
                bits.append(self._stringify_hrule(options))
                bits.append("\n")
            bits.append(options["vertical_char"])
        for field, width, in zip(self._field_names, self._widths):
            if options["fields"] and field not in options["fields"]:
                continue
            if self._align[field] == "l":
                bits.append(" " * lpad + unicode(field).ljust(width) + " " * rpad)
            elif self._align[field] == "r":
                bits.append(" " * lpad + unicode(field).rjust(width) + " " * rpad)
            else:
                bits.append(" " * lpad + unicode(field).center(width) + " " * rpad)
            if options["border"]:
                bits.append(options["vertical_char"])
        if options["border"] and options["hrules"] != NONE:
            bits.append("\n")
            bits.append(self._stringify_hrule(options))
        return "".join(bits)

    def _stringify_row(self, row, options):

        bits = []
        lpad, rpad = self._get_padding_widths(options)
        if options["border"]:
            bits.append(self.vertical_char)
        for field, value, width, in zip(self._field_names, row, self._widths):
            if options["fields"] and field not in options["fields"]:
                continue
            if self._align[field] == "l":
                bits.append(" " * lpad + unicode(value).ljust(width) + " " * rpad)
            elif self._align[field] == "r":
                bits.append(" " * lpad + unicode(value).rjust(width) + " " * rpad)
            else:
                bits.append(" " * lpad + unicode(value).center(width) + " " * rpad)
            if options["border"]:
                bits.append(self.vertical_char)
        if options["border"] and options["hrules"]== ALL:
            bits.append("\n")
            bits.append(self._stringify_hrule(options))
        return "".join(bits)

    ##############################
    # HTML PRINT/STRING METHODS  #
    ##############################

    def print_html(self, **kwargs):

        """Print HTML formatted version of table in current state to stdout.

        Arguments:

        start - index of first data row to include in output
        end - index of last data row to include in output PLUS ONE (list slice style)
        fields - names of fields (columns) to include
        sortby - name of field to sort rows by
        format - should be True or False to attempt to format alignmet, padding, etc. or not
        header - should be True or False to print a header showing field names or not
        border - should be True or False to print or not print borders
        hrules - include horizontal rule after each row
        attributes - dictionary of name/value pairs to include as HTML attributes in the <table> tag"""

        print self.get_html_string(**kwargs)

    def get_html_string(self, **kwargs):

        """Return string representation of HTML formatted version of table in current state.

        Arguments:

        start - index of first data row to include in output
        end - index of last data row to include in output PLUS ONE (list slice style)
        fields - names of fields (columns) to include
        sortby - name of 
        border - should be True or False to print or not print borders
        format - should be True or False to attempt to format alignmet, padding, etc. or not
        header - should be True or False to print a header showing field names or not
        border - should be True or False to print or not print borders
        hrules - include horizontal rule after each row
        attributes - dictionary of name/value pairs to include as HTML attributes in the <table> tag"""

        options = self._get_options(kwargs)

        if self._caching:
            key = cPickle.dumps(options)
            if key in self.html_cache:
                return self.html_cache[key]

        if options["format"]:
            string = self._get_formatted_html_string(options)
        else:
            string = self._get_simple_html_string(options)

        if self._caching:
            self.html_cache[key] = string

        return string

    def _get_simple_html_string(self, options):

        bits = []
        # Slow but works
        table_tag = '<table'
        if options["border"]:
            table_tag += ' border="1"'
        if options["attributes"]:
            for attr_name in options["attributes"]:
                table_tag += ' %s="%s"' % (attr_name, options["attributes"][attr_name])
        table_tag += '>'
        bits.append(table_tag)
        # Headers
        bits.append("    <tr>")
        for field in self._field_names:
            if options["fields"] and field not in options["fields"]:
                continue
            bits.append("        <th>%s</th>" % cgi.escape(unicode(field)))
        bits.append("    </tr>")
        # Data
        if options["sortby"]:
            rows = self._get_sorted_rows(options)
        else:
            rows = self._rows
        for row in self._rows:
            bits.append("    <tr>")
            for field, datum in zip(self._field_names, row):
                if options["fields"] and field not in options["fields"]:
                    continue
                bits.append("        <td>%s</td>" % cgi.escape(unicode(datum)))
        bits.append("    </tr>")
        bits.append("</table>")
        string = "\n".join(bits)

        return string

    def _get_formatted_html_string(self, options):

        bits = []
        lpad, rpad = self._get_padding_widths(options)
        # Slow but works
        table_tag = '<table'
        if options["border"]:
            table_tag += ' border="1"'
        if options["hrules"] == NONE:
            table_tag += ' frame="vsides" rules="cols"'
        if options["attributes"]:
            for attr_name in options["attributes"]:
                table_tag += ' %s="%s"' % (attr_name, options["attributes"][attr_name])
        table_tag += '>'
        bits.append(table_tag)
        # Headers
        if options["header"]:
            bits.append("    <tr>")
            for field in self._field_names:
                if options["fields"] and field not in options["fields"]:
                    continue
                bits.append("        <th style=\"padding-left: %dem; padding-right: %dem; text-align: center\">%s</th>" % (lpad, rpad, cgi.escape(unicode(field))))
            bits.append("    </tr>")
        # Data
        if options["sortby"]:
            rows = self._get_sorted_rows(options)
        else:
            rows = self._rows
        for row in self._rows:
            bits.append("    <tr>")
            for field, datum in zip(self._field_names, row):
                if options["fields"] and field not in options["fields"]:
                    continue
                if self._align[field] == "l":
                    bits.append("        <td style=\"padding-left: %dem; padding-right: %dem; text-align: left\">%s</td>" % (lpad, rpad, cgi.escape(unicode(datum))))
                elif self._align[field] == "r":
                    bits.append("        <td style=\"padding-left: %dem; padding-right: %dem; text-align: right\">%s</td>" % (lpad, rpad, cgi.escape(unicode(datum))))
                else:
                    bits.append("        <td style=\"padding-left: %dem; padding-right: %dem; text-align: center\">%s</td>" % (lpad, rpad, cgi.escape(unicode(datum))))
        bits.append("    </tr>")
        bits.append("</table>")
        string = "\n".join(bits)

        return string

def main():

    x = PrettyTable(["City name", "Area", "Population", "Annual Rainfall"])
    x.align["City name"] = "l" # Left align city names
    x.add_row(["Adelaide",1295, 1158259, 600.5])
    x.add_row(["Brisbane",5905, 1857594, 1146.4])
    x.add_row(["Darwin", 112, 120900, 1714.7])
    x.add_row(["Hobart", 1357, 205556, 619.5])
    x.add_row(["Sydney", 2058, 4336374, 1214.8])
    x.add_row(["Melbourne", 1566, 3806092, 646.9])
    x.add_row(["Perth", 5386, 1554769, 869.4])
    print x

if __name__ == "__main__":
    main()
