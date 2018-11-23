# This is: AutoProcess

.PHONY: all docs rpm srpm spec tar upload upload-sources upload-srpms upload-rpms
.SILENT:

# version of the program
VERSION := 'v201811'
RELEASE = 1
SOURCE = autoprocess-$(VERSION).tar

all: archive

#
#	aliases
#
# TODO: does making an rpm depend on making a .srpm first ?
tar: $(SOURCE)
	# do nothing
#
#	archive
#
archive: 
	@echo Running git archive...
	# use HEAD if tag doesn't exist yet, so that development is easier...
	git archive --prefix=autoprocess-$(VERSION)/ -o $(SOURCE) $(VERSION) 2> /dev/null || (echo 'Warning: $(VERSION) does not exist! Using HEAD.' && git archive --prefix=autoprocess-$(VERSION)/ -o $(SOURCE) HEAD)
	# TODO: if git archive had a --submodules flag this would easier!
	@echo Running git archive submodules...
	# i thought i would need --ignore-zeros, but it doesn't seem necessary!
	p=`pwd` && (echo .; git submodule foreach) | while read entering path; do \
		temp="$${path%\'}"; \
		temp="$${temp#\'}"; \
		path=$$temp; \
		[ "$$path" = "" ] && continue; \
		(cd $$path && git archive --prefix=autoprocess-$(VERSION)/$$path/ HEAD > $$p/tmp.tar && tar --concatenate --file=$$p/$(SOURCE) $$p/tmp.tar && rm $$p/tmp.tar && gzip $$p/$(SOURCE)); \
	done

# vim: ts=8
