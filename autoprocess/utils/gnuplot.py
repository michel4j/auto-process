import subprocess


def plot(data, plot_type='linespoints', style='full-height'):
    raw_data = []
    raw_data.append(data['x'])
    raw_data.extend(data['y1'])
    y2_start = len(raw_data)
    raw_data.extend(data.get('y2', []))
    data_array = list(zip(*raw_data))
    labels = data_array[0]

    height = 43 if style == 'full-height' else 24
    if data.get('x-scale') == 'inv-square':
        xspec = '($1**-2)'
        extras = [
            'set xtics nomirror',
            'set link x via 1/x**2 inverse 1/x**0.5',
            'set x2tics'
        ]
        extras = []
    else:
        xspec = '1'
        extras = []

    plots = [
                "'-' using {}:{} title '{}' with {} axes x1y1 ".format(xspec, i + 2, labels[i], plot_type)
                for i in range(y2_start)
            ] + [
                "'-' using {}:{} title '{}' with {} axes x1y2 ".format(xspec, i + 2, labels[i], plot_type)
                for i in range(y2_start, len(raw_data))
            ]
    plot_data = '\n'.join([
        '\t '.join(['{}'.format(val) for val in row])
        for row in data_array[1:]
    ])
    commands = "\n".join(extras + [
        "set term dumb 110 {}".format(height),
        "plot " + ',\n\t'.join(plots),
        plot_data,
        "exit"
    ])

    process = subprocess.Popen(['gnuplot'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    output, errors = process.communicate(commands.encode('utf8'))
    return output  # .decode('utf-8')
