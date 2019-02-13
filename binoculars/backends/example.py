import sys
import os
import itertools
import numpy as np

from .. import backend, errors, util


'''
This example backend contains the minimal set of functions needed to construct a backend.
It consists of a child of a backend.InputBase class and a child of a backend.ProjectionBase
class. The backend.Inputbase is collects the data from the measurement. The backend.ProjectionBase
class calculates the new coordinates per pixel.

You can write as much input classes and as much projections in one backend as you prefer, provided that
the output of the inputclass is compatible with projection class. Otherwise you will be
served best by writing a new backend, for the incompatibility will create errors that break the script.
In the configuration file you specify the inputclass and projection needed for the treatment of the dataset.
'''


class QProjection(backend.ProjectionBase):
    def project(self, wavelength, af, delta, omega, ai):
        '''
        This class takes as input the tuple of coordinates returned by the process_job
        method in the backend.InputBase class. Here you specify how to project the coordinates
        that belong to every datapoint. The number of input arguments should match the
        second tuple returned by process_job. The shape of each returned array should match
        the shape of the first argument returned by process_job
        '''

        k0 = 2 * np.pi / wavelength

        qy = k0 * (np.cos(af) * np.cos(delta) - np.cos(ai) * np.cos(omega))
        qx = k0 * (np.cos(af) * np.sin(delta) - np.cos(ai) * np.sin(omega))
        qz = k0 * (np.sin(af) + np.sin(ai))

        return (qx.flatten(), qy.flatten(), qz.flatten()) # a tuple of np.arrays with the same dimension as the number of labels

    def get_axis_labels(self):
        '''
        Specify the names of the axes. The number of labels should be equal to the number
        of arrays returned in the project method.
        '''
        return 'qx', 'qy', 'qz'


class Input(backend.InputBase):
    def generate_jobs(self, command):
        '''
        Command is supplied when the program is started in the terminal. This can used to differentiate between separate datasets
        that will be processed independently.
        '''

        scans = util.parse_multi_range(','.join(command).replace(' ', ','))# parse the command
        for scanno in scans:
            yield backend.Job(scan=scanno)

    def process_job(self, job):
        '''
        This methods is a generator that returns the intensity, the weights and a tuple of coordinates that
        will be used for projection. The input is a backend.job object. This objects contains attributes that are supplied
        as keyword arguments in the generate_jobs method when backend.Job is instantiated. You can wet here the weights according
        the behaviour of your detector. To select normal averaging give the weights the value of ones. This array should be the same shape as
        the intensity array.

        This example backend simulates a random path through angular space starting at the origin.
        an example image will be generated using a three dimensional 10-slit interference function.
        The angles are with respect to the sample where af and delta are the angular coordinates
        of the pixels and ai and omega are the in plane and out of plane angles of the incoming beam.
        '''
        super(Input, self).process_job(job)# call super to fix metadeta handling
        scan = job.scan

        #reflects a scan with 100 datapoints
        aaf    = np.linspace(0, np.random.random() * 20, 100)
        adelta = np.linspace(0, np.random.random() * 20, 100)
        aai = np.linspace(0, np.random.random() * 20, 100)
        aomega = np.linspace(0, np.random.random() * 20, 100)
        for af, delta, ai, omega in zip(aaf, adelta, aai, aomega):
            print('af: {0}, delta: {1}, ai: {2}, omega: {3}'.format(af, delta, ai, omega))

            # caculating the angles per pixel. The values specified in the configuration file
            # can be used for calculating these values
            pixelsize = np.array(self.config.pixelsize)
            sdd = self.config.sdd
            app = np.arctan(pixelsize / sdd) * 180 / np.pi

            # create an image of 100 x 100 pixels and calculate the coordinates corresponding to every pixel
            centralpixel = self.config.centralpixel # (column, row) = (delta, af)
            af_range= -app[1] * (np.arange(100) - centralpixel[1]) + af
            delta_range= app[0] * (np.arange(100) - centralpixel[0]) + delta

            #calculating the coordinates for simulating the image. This is only included
            #in this example for simulating of the images. It has no other use.

            k0 = 2 * np.pi / self.config.wavelength
            delta, af = np.meshgrid(delta_range, af_range)
            ai *= np.pi/180
            delta *= np.pi/180
            af *= np.pi/180
            omega *= np.pi/180

            qy = k0 * (np.cos(af) * np.cos(delta) - np.cos(ai) * np.cos(omega))
            qx = k0 * (np.cos(af) * np.sin(delta) - np.cos(ai) * np.sin(omega))
            qz = k0 * (np.sin(af) + np.sin(ai))

            #simulating the image
            data = np.abs(np.sin(qx * 10) / np.sin(qx) * np.sin(qy * 10) / np.sin(qy) * np.sin(qz * 10) / np.sin(qz))**2
            weights = np.ones_like(data)

            yield data, weights, (self.config.wavelength, af, delta, omega, ai)

    def parse_config(self, config):
        '''
        To collect and process data you need the values provided in the configuration file.
        These you can access locally through the provided config object. This is a dict with
        as keys the labels given in the configfile. To use them outside the parse_config method you attribute them
        to the self.config object which can be used throughout the input class. A warning will be
        generated afterwards for config values not popped out of the dict.
        '''
        super(Input, self).parse_config(config)
        self.config.sdd = float(config.pop('sdd'))
        self.config.pixelsize = util.parse_tuple(config.pop('pixelsize'), length=2, type=float)
        self.config.centralpixel = util.parse_tuple(config.pop('centralpixel'), length=2, type=int)
        self.config.wavelength = float(config.pop('wavelength'))


    def get_destination_options(self, command):
        '''
        Creates the arguments that you can use to construct an output filename. This method returns
        a dict object with keys that will can be  used in the configfile. In the configfile the output
        filename can now be described as 'destination = demo_{first}-{last}.hdf5'.
        This helps to organise the output automatically.
        '''
        if not command:
            return False
        command = ','.join(command).replace(' ', ',')
        scans = util.parse_multi_range(command)
        return dict(first=min(scans), last=max(scans), range=','.join(command))


