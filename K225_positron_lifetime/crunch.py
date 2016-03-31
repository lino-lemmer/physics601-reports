#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright © 2013-2014, 2016 Martin Ueding <dev@martin-ueding.de>
# Licensed under The GNU Public License Version 2 (or later)

import argparse
import json
import os
import random
import re
import sys
import glob

import matplotlib.pyplot as pl
import numpy as np
import scipy.interpolate
import scipy.misc
import scipy.ndimage.filters
import scipy.optimize as op
import scipy.stats
import mpl_toolkits.mplot3d.axes3d as p3

from unitprint2 import siunitx
import bootstrap

import spectrum
import time_gauge

TEMP_PATTERN = re.compile('in-(\d+(?:,\d+)?)-(\d+(?:,\d+)?)C\.txt')


def dandify_plot():
    '''
    Common operations to make matplotlib plots look nicer.
    '''
    pl.grid(True)
    pl.margins(0.05)
    pl.tight_layout()


def get_temp(filename):
    '''
    Retrieves the temperatures stored in the filename itself.

    :param str filename: Filename or full path
    :returns tuple(str): Tuple with upper and lower temperature.

    >>> get_temp('in-102,5-104,2C.txt')
    (102.5, 104.2)
    >>> get_temp('in-102-104,2C.txt')
    (102.0, 104.2)
    >>> get_temp('in-102,5-104C.txt')
    (102.5, 104.0)
    '''
    basename = os.path.basename(filename)
    m = TEMP_PATTERN.match(basename)
    if m:
        first = float(m.group(1).replace(',', '.'))
        second = float(m.group(2).replace(',', '.'))

        return (first, second)

    return None




def prepare_for_pgf(filename, lower=0, upper=8000, error=False):
    '''
    Converts raw data for use with pgfplots, reduces data.
    '''
    data = np.loadtxt('Data/{}.txt'.format(filename))
    channel = data[:,0]
    counts = data[:,1]
    step = 10
    channel_sel = channel[lower:upper:step]
    counts_sel = counts[lower:upper:step]

    if error:
        to_save = bootstrap.pgfplots_error_band(channel_sel,
                                                counts_sel,
                                                np.sqrt(counts_sel))
    else:
        to_save = np.column_stack([channel_sel, counts_sel])
    np.savetxt('_build/xy/{}.txt'.format(filename), to_save)

    pl.plot(channel, counts, linestyle="none", marker="o")
    dandify_plot()
    pl.savefig('_build/mpl-channel-counts-{}.pdf'.format(filename))
    pl.clf()


def prepare_files(T):
    prepare_for_pgf('lyso-li', error=True)
    prepare_for_pgf('lyso-re', error=True)
    prepare_for_pgf('na-li', error=True)
    prepare_for_pgf('na-re', error=True)
    prepare_for_pgf('na-511-re')
    prepare_for_pgf('na-511-li')
    prepare_for_pgf('na-1275-li')


def job_time_gauge(T, show_gauss=False, show_lin=False):


    # linear fit with delete-1-jackknife

    # files for fit and plot of time gauge 
    x = np.linspace(750, 4000, 100)
    y = linear(x, slope_val, intercept_val)

    np.savetxt('_build/xy/time_gauge_plot.txt', np.column_stack([channel_val,time , channel_err]))
    np.savetxt('_build/xy/time_gauge_fit.txt', np.column_stack([x,y]))
        

    T['time_gauge_slope'] = siunitx(slope_val*1e3, slope_err*1e3)
    T['time_gauge_intercept'] = siunitx(intercept_val, intercept_err)

    # time resolution

    T['width_6'] = siunitx(width_val , width_err)
    FWHM_val = 2*np.sqrt(2*np.log(2)) * width_val 
    FWHM_err = 2*np.sqrt(2*np.log(2)) * width_err 
    T['FWHM_6'] = siunitx(FWHM_val , FWHM_err)
    
    time_res = FWHM_val * slope_val
    time_res_err = np.sqrt((FWHM_val * slope_err)**2 + (FWHM_err * slope_val)**2)
    T['time_resolution'] = siunitx(time_res , time_res_err)


def lifetime_spectra(T):
    files = glob.glob('Data/in-*.txt')

    for i in range(len(files)):
        data = np.loadtxt(files[i])
        channel = data[:,0]
        counts = data[:,1]

        mean = []
        width = []
        A_0 = []
        A_t = []
        tau_0 = []
        tau_t = []
        BG = []

        for a in range(2):
            boot_counts = redraw_count(counts)
            popt, pconv = op.curve_fit(spectrum.lifetime_spectrum, channel, boot_counts, p0=[
                1600,
                45,
                180,
                180,
                40,
                40,
                0
                ])
            mean.append(popt[0])
            width.append(popt[1])
            A_0.append(popt[2])
            A_t.append(popt[3])
            tau_0.append(popt[4])
            tau_t.append(popt[5])
            BG.append(popt[6])

        mean_val, mean_err = bootstrap.average_and_std_arrays(mean)
        width_val, width_err = bootstrap.average_and_std_arrays(width)
        A_0_val, A_0_err = bootstrap.average_and_std_arrays(A_0)
        A_t_val, A_t_err = bootstrap.average_and_std_arrays(A_t)
        tau_0_val, tau_0_err = bootstrap.average_and_std_arrays(tau_0)
        tau_t_val, tau_t_err = bootstrap.average_and_std_arrays(tau_t)
        BG_val, BG_err = bootstrap.average_and_std_arrays(BG)


    x = np.linspace(1000, 3000, 500)
    y = spectrum.lifetime_spectrum(x, mean_val, width_val, A_0_val, A_t_val, tau_0_val, tau_t_val, BG_val)

    pl.plot(channel, counts, linestyle="none", marker="o")
    pl.plot(x, y)
    dandify_plot()
    pl.savefig('_build/mpl-channel-counts.pdf')
    pl.clf()


def redraw_count(a):
    '''
    Takes a ``np.array`` with counts and re-draws the counts from the implicit
    Gaussian distribution with width ``sqrt(N)``.
    '''
    out = [random.gauss(x, np.sqrt(x)) for x in a]
    return np.array(out).reshape(a.shape)


def test_keys(T):
    '''
    Testet das dict auf Schlüssel mit Bindestrichen.
    '''
    dash_keys = []
    for key in T:
        if '-' in key:
            dash_keys.append(key)

    if len(dash_keys) > 0:
        print()
        print('**************************************************************')
        print('* Es dürfen keine Bindestriche in den Schlüsseln für T sein! *')
        print('**************************************************************')
        print()
        print('Folgende Schlüssel enthalten Bindestriche:')
        for dash_key in dash_keys:
            print('-', dash_key)
        print()
        sys.exit(100)


def main():
    T = {}

    parser = argparse.ArgumentParser()
    parser.add_argument('--show', action='store_true')
    options = parser.parse_args()

    time_gauge.job_time_gauge(T)

    prepare_files(T)
    #job_time_gauge(T)
    #lifetime_spectra(T)

    test_keys(T)
    with open('_build/template.js', 'w') as f:
        json.dump(dict(T), f, indent=4, sort_keys=True)


if __name__ == "__main__":
    main()
