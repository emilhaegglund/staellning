#!/usr/bin/env python
import os
import argparse
import poretools
import time
import timeit

from links import run_links
from sspace import run_sspace
from fastainfo import get_N50, get_contigs, get_contig_sizes

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from bokeh.io import hplot
from bokeh.plotting import figure, curdoc
from bokeh.client import push_session
from bokeh.models import ColumnDataSource, HoverTool

import numpy as np
from numpy import pi


def scaffolding_time(args, list_of_files):
    """Use timer to start scaffolding process.

    Args:
        args: Object with command line arguments.
        list_of_files (list): List with filenames
    
    Returns:
    """
    global tic
    toc = timeit.default_timer()
    if toc - tic > int(args.intensity):
        scaffolds = run_scaffold(args, list_of_files)
        print("Scaffolds: " + str(scaffolds))
        if scaffolds <= args.stop:
            stop()
        tic = timeit.default_timer()


def scaffolding_reads(args, list_of_files, counter, completed):
    """Use read counts to start scaffolding process.

    Args:
        args: Object with command line arguments.
        list_of_files (list): List with filenames
    """
    # print('Counter: ' + str(counter))
    if len(list_of_files) % int(args.intensity) == 0:
        scaffolds, counter, completed = run_scaffold(args, list_of_files, counter)
        print("Scaffolds: " + str(scaffolds))
        if scaffolds <= args.stop:
            completed = stop()
        return counter, completed
    else:
        return counter, completed


def run_scaffold(args, list_of_files, counter):
    """Start scaffolding.

    Args:
        args: Object with command line arguments.
        list_of_files (list): List with filenames
    Returns:
        number_of_scaffolds
    """
    if args.scaffolder == 'links':
        scaffolds = run_links(args.short_reads, list_of_files, args.output)
    elif args.scaffolder == 'sspace':
        scaffolds, counter, completed = run_sspace(args.short_reads, list_of_files, args.output, counter, args.genome_size)
        update(counter)
    else:

        print('Should never go here, must select a scaffolder')
    return scaffolds, counter, completed


def short_read_assembly(path):
    """ Get short read assembly data. """
    n50 = get_N50(path)
    short_read_contigs = get_contigs(path)
    contig_sizes = get_contig_sizes(path)

    short_read_assembly_data = [0, n50,
                                short_read_contigs,
                                contig_sizes]
    return short_read_assembly_data


def bokeh_plots(counter):
    """ Setup bokeh plots. """

    source = ColumnDataSource(dict(
        reads=reads_list,
        scaffolds=scaffold_list,
        n50=N50_list
    ))
    contig_src = ColumnDataSource(dict(start=[0],
                                       stop=[2*pi],
                                       colors=['green'],
                                       contigs = [0]))

    # setup bokeh-plots
    n50_plot = n50(source)
    contig_numbers_plot = contig_numbers(source)
    contig_circle_plot = contig_circle(contig_src)
    layout = hplot(contig_numbers_plot,
                   n50_plot,
                   contig_circle_plot)
    session = push_session(curdoc())
    session.show()


def n50(source):
    """ Create N50 plot."""
    plot = figure(y_range=(0, 1500000))
    plot.x_range.follow = "end"
    plot.x_range.follow_interval = 500
    plot.circle(x='reads', y='n50', source=source, size=12, color='red')
    plot.line(x='reads', y='n50', source=source, color='red')
    plot.title = 'N50 values'
    plot.xaxis.axis_label = 'Reads'
    plot.yaxis.axis_label = 'N50'

    return plot


def contig_numbers(source):
    """Create contig number plot. """
    plot = figure(y_range=(0, 50))
    plot.x_range.follow = "end"
    plot.x_range.follow_interval = 500
    plot.circle(x='reads', y='scaffolds', source=source, size=10)
    plot.line(x='reads', y='scaffolds', source=source)
    plot.title = 'Number of contigs'
    plot.xaxis.axis_label = 'Reads'
    plot.yaxis.axis_label = 'Contigs'

    return plot


def contig_circle():
    """ Create contig circle. """
    hover = HoverTool(tooltips=[
                ('Length', '@contigs')])
    hover.point_policy = "follow_mouse"
    plot = figure(x_axis_type=None, y_axis_type=None, tools=[hover])
    plot.annular_wedge(x=0, y=0, inner_radius=0.5, outer_radius=0.7,
                       start_angle='start', end_angle='stop', color='colors',
                       alpha=0.9, source=contig_src)
    plot.title = 'Contig lengths'
    return plot


def update(counter):
    """ Stream new data to bokeh-plot.
    """
    total = 2*pi
    contigs = []
    for keys in counter[4]:
        contigs.append(counter[4][keys])
    cum_contig_length = sum(contigs)
    contig_fractions = [float(contig)/cum_contig_length for contig in contigs]
    contig_lengths = [contig * total for contig in contig_fractions]
    x = np.random.random(size=counter[3][-1]) * 100
    y = np.random.random(size=counter[3][-1]) * 100
    colors = [
        "#%02x%02x%02x" % (int(r), int(g), 100) for r, g in zip(50+2*x, 30+2*y)
    ]

    start = []
    stop = []
    start_pos = 0
    total_length = 0
    for i in range(len(contig_lengths)):
        start.append(start_pos)
        start_pos += contig_lengths[i]
        total_length += contig_lengths[i]
        stop.append(total_length)

    new_data = dict(
        reads=[counter[2][-1]],
        scaffolds=[counter[3][-1]],
        n50=[counter[1][-1]],
        )
    contig_new_data = dict(
        start = start,
        stop = stop,
        colors = colors,
        contigs = contigs 
        )
    source.stream(new_data, 400)
    contig_src.remove('start')
    contig_src.remove('stop')
    contig_src.remove('colors')
    contig_src.remove('contigs')
    contig_src.add([], name='start')
    contig_src.add([], name='stop')
    contig_src.add([], name='colors')
    contig_src.add([], name='contigs')
    contig_src.stream(contig_new_data)
    print('Update plot')


def stop():
    """ Stop sequencing.
    """
    completed = True
    print("Stop sequencing")
    return completed


def parse_arguments():
    """Parse command line arguments.

    Return:
        args: Object with command line arguments.
    """
    parser = argparse.ArgumentParser(description='Scaffold genomes\
                                                  in real time')
    parser.add_argument('--scaffolder', '-s', required=True,
                        choices=['links', 'sspace'],
                        help='Which scaffolder tu use')
    parser.add_argument('--assembly', '-a',
                        help='Try to assembly reads with canu')
    parser.add_argument('--watch', '-w', required=True,
                        help='Directory to watch for fast5 files')
    parser.add_argument('--short_reads', '-c', required=True,
                        help='Path to short read file')
    parser.add_argument('--run_mode', '-r', required=True,
                        choices=['time', 'reads'],
                        help='Use timer or read count')
    parser.add_argument('--intensity', '-i', required=True,
                        help='How often to run the assembler')
    parser.add_argument('--stop', '-q', required=True,
                        help='Stop minION when this number of scaffolds\
                        has been reached.')
    parser.add_argument('--genome_size', '-g', required=True,
                        help='Stop MinION when a scaffold is within 10% of this\
                        value.')
    parser.add_argument('--output', '-o', required=True,
                        help='Output directory for scaffold files')

    args = parser.parse_args()

    return args


class Fast5Handler(PatternMatchingEventHandler):
    patterns = ["*.fast5"]

    def on_created(self, event):
        """ Write files to fasta and scaffold. """
        self.write_to_fasta(event)

    def write_to_fasta(self, event):
        """Convert fast5 to fasta if there is a 2D read
           and scaffold.
        """
        fast5_file = poretools.Fast5File(event.src_path)
        # print("In write to fasta function")
        # print('Processing: ' + event.src_path)
        if fast5_file.has_2D():
            # Get a filename for the fasta file
            filename_list = list(event.src_path)
            # Change file format from fast5 to fasta
            filename_list[-1] = 'a'
            filename = ''.join(filename_list)
            seq = fast5_file.get_fastas('2D')
            with open(filename, 'w') as fasta_file:
                fasta_file.write(str(seq[0]))
            list_of_files.append(filename)
            print('Number of fasta files: ' + str(len(list_of_files)))
            print('Number of 2D reads:' + str(len(list_of_files)))
            if args.run_mode == 'time':
                scaffolding_time(args, list_of_files)
            else:
                global counter, completed
                counter, completed = scaffolding_reads(args, list_of_files,
                                                       counter, completed)

if __name__ == '__main__':
    list_of_files = []
    global completed
    completed = False
    args = parse_arguments()
    if args.run_mode == 'time':
        # Must use global timer.
        global tic
        tic = timeit.default_timer()

    # Listen for Fast5 files in dir
    # This must be setup from short read assemblie information
    # Setup initial counter

    N50_list = [90152]
    reads_list = [0]
    scaffold_list = [44]
    global counter
    # counter = short_assembly(args.short_reads)
    counter = [0, N50_list, reads_list, scaffold_list, None]

    # start_bokeh_server()
    bokeh_plots(counter)

    # create and start observer
    observer1 = Observer()
    observer1.schedule(Fast5Handler(), path=args.watch)
    observer1.start()

   
    while not completed:
        time.sleep(1)
    print('Completed!')
    observer1.stop()
    observer1.join()
