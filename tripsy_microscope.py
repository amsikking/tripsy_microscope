# Imports from the python standard library:
import atexit
import os
import queue
import time
from datetime import datetime

# Third party imports, installable via pip:
import napari
import numpy as np
from tifffile import imread, imwrite

# Our code, one .py file per module, copy files to your local directory:
try:
    import concurrency_tools as ct  # github.com/AndrewGYork/tools
    import ni_PCI_6733              # github.com/amsikking/ni_PCI_6733
    import pco_panda42_bi           # github.com/amsikking/pco_panda42_bi
    import sutter_Lambda_10_3       # github.com/amsikking/sutter_Lambda_10_3
    from napari_in_subprocess import display    # github.com/AndrewGYork/tools
except Exception as e:
    print('tripsy_microscope.py -> One or more imports failed')
    print('tripsy_microscope.py -> error =',e)

# optical configuration (edit as needed):
epi_dichroic_mirror_options = {'488 dichroic (part#)'   :0,
                               '(unused)'               :1}
epi_emission_filter_options = {'488 filter (part#)'     :0,
                               '(unused)'               :1}

tbl_dichroic_mirror_options = {'785 dichroic (part#)'   :0,
                               '(unused)'               :1}
tbl_emission_filter_options = {'Shutter'                :0,
                               'Open'                   :1,
                               '785 filter (part#)'     :2,
                               '(unused)'               :3,
                               '(unused)'               :4,
                               '(unused)'               :5,
                               '(unused)'               :6,
                               '(unused)'               :7,
                               '(unused)'               :8,
                               '(unused)'               :9}

class Microscope:
    def __init__(self,
                 max_allocated_bytes,   # Limit of available RAM for machine
                 ao_rate,               # slow ~1e3, medium ~1e4, fast ~1e5
                 name='TRIPSY v1.0',
                 verbose=True,
                 print_warnings=True):
        self.max_allocated_bytes = max_allocated_bytes
        self.name = name
        self.verbose = verbose
        self.print_warnings = print_warnings
        if self.verbose: print("%s: opening..."%self.name)
        self.unfinished_tasks = queue.Queue()
        # init hardware/software:
        slow_fw_init = ct.ResultThread(
            target=self._init_filter_wheel).start() #~5.3s
        slow_camera_init = ct.ResultThread(
            target=self._init_cameras).start()      #~3.6s
        slow_lasers_init = ct.ResultThread(
            target=self._init_lasers).start()       #~0.25s
        self._init_display()                        #~1.3s
        self._init_ao(ao_rate)                      #~0.2s
        slow_lasers_init.get_result()
        slow_camera_init.get_result()
        slow_fw_init.get_result()
        # set epi defaults:
        # -> epi_apply_settings args
        self.epi_dichroic_mirror='488 dichroic (part#)',
        self.epi_emission_filter='488 filter (part#)',
        self.epi_timestamp_mode = "binary+ASCII"
        self.epi_camera._set_timestamp_mode(self.epi_timestamp_mode)
        self.epi_camera_preframes = 1 # ditch noisy frames before recording?
        self.epi_max_bytes_per_buffer = (2**31) # legal tiff
        self.epi_max_data_buffers = 3 # camera, display, filesave
        # -> epi additional
        self.epi_num_active_data_buffers = 0
        self._epi_settings_applied = False
        # set tbl defaults:
        # -> tbl_apply_settings args
        self.tbl_dichroic_mirror='488 dichroic (part#)',
        self.tbl_emission_filter='488 filter (part#)',
        self.tbl_timestamp_mode = "binary+ASCII"
        self.tbl_camera._set_timestamp_mode(self.tbl_timestamp_mode)
        self.tbl_camera_preframes = 1 # ditch noisy frames before recording?
        self.tbl_max_bytes_per_buffer = (2**31) # legal tiff
        self.tbl_max_data_buffers = 3 # camera, display, filesave
        # -> tbl additional
        self.tbl_num_active_data_buffers = 0
        self._tbl_settings_applied = False
        # switch to epi:
        self._switch_microscopes(epi_enabled=True)
        if self.verbose: print("\n%s: -> open and ready."%self.name)

    def _init_filter_wheel(self):
        if self.verbose: print("\n%s: opening filter wheel..."%self.name)
##        self.filter_wheel = sutter_Lambda_10_3.Controller(
##            which_port='COM3', verbose=False)
        if self.verbose: print("\n%s: -> filter wheel open."%self.name)
##        atexit.register(self.filter_wheel.close)

    def _init_cameras(self):
        if self.verbose: print("\n%s: opening cameras..."%self.name)
        # init the cameras in the correct order:
        self.epi_camera = ct.ObjectInSubprocess(
            pco_panda42_bi.Camera,
            verbose=False,
            close_method_name='close')
        self.tbl_camera = ct.ObjectInSubprocess(
            pco_panda42_bi.Camera,
            verbose=False,
            close_method_name='close')
        if self.verbose: print("\n%s: -> camera open."%self.name)

    def _init_lasers(self):
        if self.verbose: print("\n%s: opening lasers..."%self.name)
        self.laser_names = ('488', '785', '830', '915', '940')
##        self.laser_box = lumencor_Spectra_X.Controller(
##            which_port='COM5', led_names=self.led_names, verbose=False)
        if self.verbose: print("\n%s: -> lasers open."%self.name)
##        atexit.register(self.laser_box.close)

    def _init_display(self):
        if self.verbose: print("\n%s: opening display..."%self.name)
        self.display = display(display_type=_CustomNapariDisplay)
        if self.verbose: print("\n%s: -> display open."%self.name)

    def _init_ao(self, ao_rate):
        self.illumination_sources = tuple( # controlled by ao
            ['490_LED'] + [laser for laser in self.laser_names])
        self.names_to_voltage_channels = {
            'epi_camera_TTL'    : 0,
            'tbl_camera_TTL'    : 1,
            '490_LED_power'     : 2,
            '488_TTL'           : 3,
            '488_power'         : 4,
            '785_TTL'           : 5,
            '785_power'         : 6,
            '830_TTL'           : 7,
            '830_power'         : 8,
            '915_TTL'           : 9,
            '915_power'         :10,
            '940_TTL'           :11,
            '940_power'         :12,
            }
        if self.verbose: print("\n%s: opening ao card..."%self.name)
        self.ao = ct.ObjectInSubprocess(
            ni_PCI_6733.DAQ,
            num_channels=8,
            rate=ao_rate,
            verbose=False,
            close_method_name='close')
        if self.verbose: print("\n%s: -> ao card open."%self.name)
        atexit.register(self.ao.close)

    def _plot_voltages(self):
        import matplotlib.pyplot as plt
        # Reverse lookup table; channel numbers to names:
        c2n = {v:k for k, v in self.names_to_voltage_channels.items()}
        for c in range(self.voltages.shape[1]):
            plt.plot(self.voltages[:, c], label=c2n.get(c, f'ao-{c}'))
        plt.legend(loc='upper right')
        xlocs, xlabels = plt.xticks()
        plt.xticks(xlocs, [self.ao.p2s(l) for l in xlocs])
        plt.ylabel('Volts')
        plt.xlabel('Seconds')
        plt.show()

    def _switch_microscopes(self, epi_enabled):
        assert type(epi_enabled) is bool
        if epi_enabled:
            if self.verbose:
                print("\n%s: -> switching path to epi...."%self.name, end='')
            time.sleep(1) # flip paths here
            if self.verbose:
                print("done.")
            self._epi_update_voltages = True
            self._epi_enabled = True
        else:
            if self.verbose:
                print("\n%s: -> switching path to tbl...."%self.name, end='')
            time.sleep(1) # flip paths here
            if self.verbose:
                print("done.")
            self._tbl_update_voltages = True
            self._epi_enabled = False
        return None

    def _epi_check_memory(self):
        # Data:
        self.epi_images = self.epi_images_per_buffer * len(
            self.epi_channels_per_image)
        self.epi_bytes_per_data_buffer = (
            2 * self.epi_images * self.epi_height_px * self.epi_width_px)
        self.epi_data_buffer_exceeded = False
        if self.epi_bytes_per_data_buffer > self.epi_max_bytes_per_buffer:
            self.epi_data_buffer_exceeded = True
            if self.print_warnings:
                print("\n%s: ***WARNING***: settings rejected"%self.name)
                print("%s: -> epi_data_buffer_exceeded"%self.name)
                print("%s: -> reduce settings"%self.name +
                      " or increase 'epi_max_bytes_per_buffer'")
        # Total:
        self.epi_total_bytes = (
            self.epi_bytes_per_data_buffer * self.epi_max_data_buffers)
        self.epi_total_bytes_exceeded = False
        if self.epi_total_bytes > self.max_allocated_bytes:
            self.epi_total_bytes_exceeded = True
            if self.print_warnings:
                print("\n%s: ***WARNING***: settings rejected"%self.name)
                print("%s: -> epi_total_bytes_exceeded"%self.name)
                print("%s: -> reduce settings"%self.name +
                      " or increase 'epi_max_allocated_bytes'")
        return None

    def _epi_calculate_voltages(self):
        n2c = self.names_to_voltage_channels # nickname
        # Timing information:
        exposure_px = self.ao.s2p(1e-6 * self.epi_camera.exposure_us)
        rolling_px =  self.ao.s2p(1e-6 * self.epi_camera.rolling_time_us)
        jitter_px = max(self.ao.s2p(1000e-6), 1)
        period_px = max(exposure_px, rolling_px) + jitter_px
        # Calculate voltages:
        voltages = []
        # Add preframes (if any):
        for frames in range(self.epi_camera_preframes):
            v = np.zeros((period_px, self.ao.num_channels), 'float64')
            v[:rolling_px,
              n2c['epi_camera_TTL']] = 5 # falling edge-> light on!
            voltages.append(v)
        for images in range(self.epi_images_per_buffer):
            for channel, power in zip(self.epi_channels_per_image,
                                      self.epi_power_per_channel):
                v = np.zeros((period_px, self.ao.num_channels), 'float64')
                v[:rolling_px,
                  n2c['epi_camera_TTL']] = 5 # falling edge-> light on!
                v[rolling_px:period_px - jitter_px,
                  n2c[channel + '_power']] = 4.5 * power / 100
                voltages.append(v)
        voltages = np.concatenate(voltages, axis=0)
        # Timing attributes:
        self.epi_buffer_time_s = self.ao.p2s(voltages.shape[0])
        self.epi_frames_per_s = (
            self.epi_images_per_buffer / self.epi_buffer_time_s)
        return voltages

    def _epi_prepare_to_save(
        self, filename, folder_name, description, display):
        def make_folders(folder_name):
            os.makedirs(folder_name)
            os.makedirs(folder_name + '\\epi_data')
            os.makedirs(folder_name + '\\epi_metadata')
        assert type(filename) is str
        if folder_name is None:
            folder_index = 0
            dt = datetime.strftime(datetime.now(),'%Y-%m-%d_%H-%M-%S')
            folder_name = dt + '_%03i_tbl'%folder_index
            while os.path.exists(folder_name): # check overwriting
                folder_index +=1
                folder_name = dt + '_%03i_tbl'%folder_index
            make_folders(folder_name)
        else:
            if not os.path.exists(folder_name): make_folders(folder_name)
        data_path =     folder_name + '\\epi_data\\'     + filename
        metadata_path = folder_name + '\\epi_metadata\\' + filename
        # save metadata:
        to_save = {
            # date and time:
            'Date':datetime.strftime(datetime.now(),'%Y-%m-%d'),
            'Time':datetime.strftime(datetime.now(),'%H:%M:%S'),
            # args from 'acquire':
            'filename':filename,
            'folder_name':folder_name,
            'description':description,
            'display':display,
            # attributes from 'epi_apply_settings':
            # -> args
            'epi_channels_per_image':tuple(self.epi_channels_per_image),
            'epi_power_per_channel':tuple(self.epi_power_per_channel),
            'epi_dichroic_mirror':self.epi_dichroic_mirror,
            'epi_emission_filter':self.epi_emission_filter,
            'epi_illumination_time_us':self.epi_illumination_time_us,
            'epi_height_px':self.epi_height_px,
            'epi_width_px':self.epi_width_px,
            'epi_timestamp_mode':self.epi_timestamp_mode,
            'epi_images_per_buffer':self.epi_images_per_buffer,
            'epi_camera_preframes':self.epi_camera_preframes,
            'epi_max_bytes_per_buffer':self.epi_max_bytes_per_buffer,
            'epi_max_data_buffers':self.epi_max_data_buffers,
            # -> calculated
            'epi_buffer_time_s':self.epi_buffer_time_s,
            'epi_frames_per_s':self.epi_frames_per_s,
            }
        with open(os.path.splitext(metadata_path)[0] + '.txt', 'w') as file:
            for k, v in to_save.items():
                file.write(k + ': ' + str(v) + '\n')
        return data_path

    def _epi_get_data_buffer(self, shape, dtype):
        while self.epi_num_active_data_buffers >= self.epi_max_data_buffers:
            time.sleep(1e-3) # 1.7ms min
        # Note: this does not actually allocate the memory. Allocation happens
        # during the first 'write' process inside camera.record_to_memory
        data_buffer = ct.SharedNDArray(shape, dtype)
        self.epi_num_active_data_buffers += 1
        return data_buffer

    def _epi_release_data_buffer(self, shared_numpy_array):
        assert isinstance(shared_numpy_array, ct.SharedNDArray)
        self.epi_num_active_data_buffers -= 1

    def epi_apply_settings( # Must call before .acquire()
        self,
        epi_channels_per_image=None,    # Tuple of strings
        epi_power_per_channel=None,     # Tuple of floats
        epi_illumination_time_us=None,  # Float
        epi_height_px=None,             # Int
        epi_width_px=None,              # Int
        epi_timestamp_mode=None,        # "off" or "binary" or "binary+ASCII"
        epi_images_per_buffer=None,     # Int
        epi_camera_preframes=None,      # Int
        ):
        args = locals()
        args.pop('self')
        def settings_task(custody):
            custody.switch_from(None, to=self.ao) # Can change settings
            self._epi_settings_applied = False # In case the thread crashes
            # Attributes must be set previously or currently:
            for k, v in args.items():
                if v is not None:
                    setattr(self, k, v) # A lot like self.x = x
                assert hasattr(self, k), (
                    "%s: attribute %s must be set at least once"%(self.name, k))
            if (epi_height_px is not None or
                epi_width_px is not None): # legalize first
                h_px, w_px = epi_height_px, epi_width_px
                if epi_height_px is None: h_px = self.epi_height_px
                if epi_width_px is None:  w_px = self.epi_width_px
                self.epi_height_px, self.epi_width_px, self.epi_roi_px = ( 
                    pco_panda42_bi.legalize_image_size(
                        h_px, w_px, verbose=False))
            self._epi_check_memory()
            if self.epi_data_buffer_exceeded or self.epi_total_bytes_exceeded:
                custody.switch_from(self.ao, to=None)
                return None
            # Send hardware commands, slowest to fastest:
            if (epi_height_px is not None or
                epi_width_px is not None or
                epi_illumination_time_us is not None):
                self.epi_camera._disarm()
                self.epi_camera._set_roi(self.epi_roi_px) # height_px updated
                self.epi_camera._set_exposure_time_us(int(
                    self.epi_illumination_time_us +
                    self.epi_camera.rolling_time_us))
                self.epi_camera._arm(self.epi_camera._num_buffers)
            if epi_timestamp_mode is not None:
                self.epi_camera._set_timestamp_mode(epi_timestamp_mode)
            if (epi_channels_per_image is not None or
                epi_power_per_channel is not None or
                epi_height_px is not None or
                epi_illumination_time_us is not None or
                epi_images_per_buffer is not None or
                epi_camera_preframes is not None):
                for channel in self.epi_channels_per_image:
                    assert channel in self.illumination_sources
                assert len(self.epi_power_per_channel) == (
                    len(self.epi_channels_per_image))
                for i, p in enumerate(self.epi_power_per_channel):
                    assert 0 <= p <= 100
                assert type(self.epi_images_per_buffer) is int
                assert self.epi_images_per_buffer > 0
                assert type(self.epi_camera_preframes) is int
                self.epi_camera.num_images = ( # update attribute
                    self.epi_images + self.epi_camera_preframes)
                self.epi_voltages = self._epi_calculate_voltages()
                self._epi_update_voltages = True
            # Finalize hardware commands, fastest to slowest:
            self._epi_settings_applied = True
            custody.switch_from(self.ao, to=None) # Release camera
        settings_thread = ct.CustodyThread(
            target=settings_task, first_resource=self.epi_camera).start()
        self.unfinished_tasks.put(settings_thread)
        return settings_thread

    def epi_acquire(
        self,               # 'tcyx' format
        filename=None,      # None = no save, same string = overwrite
        folder_name=None,   # None = new folder, same string = re-use
        description=None,   # Optional metadata description
        display=True):      # Optional turn off
        def acquire_task(custody):
            custody.switch_from(None, to=self.ao) # get ao
            if not self._epi_settings_applied:
                if self.print_warnings:
                    print("\n%s: ***WARNING***: settings not applied"%self.name)
                    print("%s: -> please apply legal epi settings"%self.name)
                    print("%s: (all arguments must be specified at least once)")
                custody.switch_from(self.ao, to=None)
                return
            if not self._epi_enabled:
                self._switch_microscopes(epi_enabled=True)
            # must write and play each time with the ni_PCI_6733 card/adaptor:
            if self._epi_update_voltages: # update if needed
                write_voltages_thread = ct.ResultThread(
                    target=self.ao._write_voltages,
                    args=(self.epi_voltages,)).start()
            if filename is not None:
                prepare_to_save_thread = ct.ResultThread(
                    target=self._epi_prepare_to_save,
                    args=(filename, folder_name, description, display)).start()
            # We have custody of the camera so attribute access is safe:
            im   = self.epi_images_per_buffer
            ch   = len(self.epi_channels_per_image)
            h_px = self.epi_height_px
            w_px = self.epi_width_px
            ti   = self.epi_images + self.epi_camera_preframes
            data_buffer = self._epi_get_data_buffer((ti, h_px, w_px), 'uint16')
            if self._epi_update_voltages:
                write_voltages_thread.get_result()
                self._epi_update_voltages = False
            # camera.record_to_memory() blocks, so we use a thread:
            camera_thread = ct.ResultThread(
                target=self.epi_camera.record_to_memory,
                kwargs={'allocated_memory': data_buffer,
                        'software_trigger': False},).start()
            # Race condition: the camera starts with (typically 16) single
            # frame buffers, which are filled by triggers from
            # ao.play_voltages(). The camera_thread empties them, hopefully
            # fast enough that we never run out. So far, the camera_thread
            # seems to both start on time, and keep up reliably once it starts,
            # but this could be fragile. The camera thread (effectively)
            # acquires shared memory as it writes to the allocated buffer.
            # On this machine the memory acquisition is faster than the camera
            # (~4GB/s vs ~1GB/s) but this could also be fragile if another
            # process interferes.
            self.ao.play_voltages(block=False)
            camera_thread.get_result()
            # Acquisition is 3D, but display and filesaving are 4D:
            data_buffer = data_buffer[ # ditch preframes
                self.epi_camera_preframes:, :, :].reshape(im, ch, h_px, w_px)
            if display:
                custody.switch_from(self.ao, to=self.display)
                if self.epi_timestamp_mode == "binary+ASCII":
                    self.display.show_epi_image(data_buffer[:,:,8:,:])
                else:
                    self.display.show_epi_image(data_buffer)
                custody.switch_from(self.display, to=None)
            else:
                custody.switch_from(self.ao, to=None)
            if filename is not None:
                data_path = prepare_to_save_thread.get_result()
                if self.verbose:
                    print("%s: saving '%s'"%(self.name, data_path))
                # TODO: consider puting FileSaving in a SubProcess
                imwrite(data_path, data_buffer[:,np.newaxis,:,:,:], imagej=True)
                if self.verbose:
                    print("%s: done saving."%self.name)
            self._epi_release_data_buffer(data_buffer)
            del data_buffer
        acquire_thread = ct.CustodyThread(
            target=acquire_task, first_resource=self.ao).start()
        self.unfinished_tasks.put(acquire_thread)
        return acquire_thread

    def _tbl_check_memory(self):
        # Data:
        self.tbl_images = self.tbl_images_per_buffer * len(
            self.tbl_channels_per_image)
        self.tbl_bytes_per_data_buffer = (
            2 * self.tbl_images * self.tbl_height_px * self.tbl_width_px)
        self.tbl_data_buffer_exceeded = False
        if self.tbl_bytes_per_data_buffer > self.tbl_max_bytes_per_buffer:
            self.tbl_data_buffer_exceeded = True
            if self.print_warnings:
                print("\n%s: ***WARNING***: settings rejected"%self.name)
                print("%s: -> tbl_data_buffer_exceeded"%self.name)
                print("%s: -> reduce settings"%self.name +
                      " or increase 'tbl_max_bytes_per_buffer'")
        # Total:
        self.tbl_total_bytes = (
            self.tbl_bytes_per_data_buffer * self.tbl_max_data_buffers)
        self.tbl_total_bytes_exceeded = False
        if self.tbl_total_bytes > self.max_allocated_bytes:
            self.tbl_total_bytes_exceeded = True
            if self.print_warnings:
                print("\n%s: ***WARNING***: settings rejected"%self.name)
                print("%s: -> tbl_total_bytes_exceeded"%self.name)
                print("%s: -> reduce settings"%self.name +
                      " or increase 'tbl_max_allocated_bytes'")
        return None

    def _tbl_calculate_voltages(self):
        n2c = self.names_to_voltage_channels # nickname
        # Timing information:
        exposure_px = self.ao.s2p(1e-6 * self.tbl_camera.exposure_us)
        rolling_px =  self.ao.s2p(1e-6 * self.tbl_camera.rolling_time_us)
        jitter_px = max(self.ao.s2p(1000e-6), 1)
        period_px = max(exposure_px, rolling_px) + jitter_px
        # Calculate voltages:
        voltages = []
        # Add preframes (if any):
        for frames in range(self.tbl_camera_preframes):
            v = np.zeros((period_px, self.ao.num_channels), 'float64')
            v[:rolling_px,
              n2c['tbl_camera_TTL']] = 5 # falling edge-> light on!
            voltages.append(v)
        for images in range(self.tbl_images_per_buffer):
            for channel, power in zip(self.tbl_channels_per_image,
                                      self.tbl_power_per_channel):
                v = np.zeros((period_px, self.ao.num_channels), 'float64')
                v[:rolling_px,
                  n2c['tbl_camera_TTL']] = 5 # falling edge-> light on!
                if channel != '490_LED': # i.e. laser channels
                    v[rolling_px:period_px - jitter_px,
                      n2c[channel + '_TTL']] = 3
                v[rolling_px:period_px - jitter_px,
                  n2c[channel + '_power']] = 4.5 * power / 100
                voltages.append(v)
        voltages = np.concatenate(voltages, axis=0)
        # Timing attributes:
        self.tbl_buffer_time_s = self.ao.p2s(voltages.shape[0])
        self.tbl_frames_per_s = (
            self.tbl_images_per_buffer / self.tbl_buffer_time_s)
        return voltages

    def _tbl_prepare_to_save(
        self, filename, folder_name, description, display):
        def make_folders(folder_name):
            os.makedirs(folder_name)
            os.makedirs(folder_name + '\\tbl_data')
            os.makedirs(folder_name + '\\tbl_metadata')
        assert type(filename) is str
        if folder_name is None:
            folder_index = 0
            dt = datetime.strftime(datetime.now(),'%Y-%m-%d_%H-%M-%S')
            folder_name = dt + '_%03i_tbl'%folder_index
            while os.path.exists(folder_name): # check overwriting
                folder_index +=1
                folder_name = dt + '_%03i_tbl'%folder_index
            make_folders(folder_name)
        else:
            if not os.path.exists(folder_name): make_folders(folder_name)
        data_path =     folder_name + '\\tbl_data\\'     + filename
        metadata_path = folder_name + '\\tbl_metadata\\' + filename
        # save metadata:
        to_save = {
            # date and time:
            'Date':datetime.strftime(datetime.now(),'%Y-%m-%d'),
            'Time':datetime.strftime(datetime.now(),'%H:%M:%S'),
            # args from 'acquire':
            'filename':filename,
            'folder_name':folder_name,
            'description':description,
            'display':display,
            # attributes from 'tbl_apply_settings':
            # -> args
            'tbl_channels_per_image':tuple(self.tbl_channels_per_image),
            'tbl_power_per_channel':tuple(self.tbl_power_per_channel),
            'tbl_dichroic_mirror':self.tbl_dichroic_mirror,
            'tbl_emission_filter':self.tbl_emission_filter,
            'tbl_illumination_time_us':self.tbl_illumination_time_us,
            'tbl_height_px':self.tbl_height_px,
            'tbl_width_px':self.tbl_width_px,
            'tbl_timestamp_mode':self.tbl_timestamp_mode,
            'tbl_images_per_buffer':self.tbl_images_per_buffer,
            'tbl_camera_preframes':self.tbl_camera_preframes,
            'tbl_max_bytes_per_buffer':self.tbl_max_bytes_per_buffer,
            'tbl_max_data_buffers':self.tbl_max_data_buffers,
            # -> calculated
            'tbl_buffer_time_s':self.tbl_buffer_time_s,
            'tbl_frames_per_s':self.tbl_frames_per_s,
            }
        with open(os.path.splitext(metadata_path)[0] + '.txt', 'w') as file:
            for k, v in to_save.items():
                file.write(k + ': ' + str(v) + '\n')
        return data_path

    def _tbl_get_data_buffer(self, shape, dtype):
        while self.tbl_num_active_data_buffers >= self.tbl_max_data_buffers:
            time.sleep(1e-3) # 1.7ms min
        # Note: this does not actually allocate the memory. Allocation happens
        # during the first 'write' process inside camera.record_to_memory
        data_buffer = ct.SharedNDArray(shape, dtype)
        self.tbl_num_active_data_buffers += 1
        return data_buffer

    def _tbl_release_data_buffer(self, shared_numpy_array):
        assert isinstance(shared_numpy_array, ct.SharedNDArray)
        self.tbl_num_active_data_buffers -= 1

    def tbl_apply_settings( # Must call before .acquire()
        self,
        tbl_channels_per_image=None,    # Tuple of strings
        tbl_power_per_channel=None,     # Tuple of floats
##        tbl_emission_filter=None,       # String
        tbl_illumination_time_us=None,  # Float
        tbl_height_px=None,             # Int
        tbl_width_px=None,              # Int
        tbl_timestamp_mode=None,        # "off" or "binary" or "binary+ASCII"
        tbl_images_per_buffer=None,     # Int
        tbl_camera_preframes=None,      # Int
        ):
        args = locals()
        args.pop('self')
        def settings_task(custody):
            custody.switch_from(None, to=self.ao) # Can change settings
            self._tbl_settings_applied = False # In case the thread crashes
            # Attributes must be set previously or currently:
            for k, v in args.items():
                if v is not None:
                    setattr(self, k, v) # A lot like self.x = x
                assert hasattr(self, k), (
                    "%s: attribute %s must be set at least once"%(self.name, k))
            if (tbl_height_px is not None or
                tbl_width_px is not None): # legalize first
                h_px, w_px = tbl_height_px, tbl_width_px
                if tbl_height_px is None: h_px = self.tbl_height_px
                if tbl_width_px is None:  w_px = self.tbl_width_px
                self.tbl_height_px, self.tbl_width_px, self.tbl_roi_px = ( 
                    pco_panda42_bi.legalize_image_size(
                        h_px, w_px, verbose=False))
            self._tbl_check_memory()
            if self.tbl_data_buffer_exceeded or self.tbl_total_bytes_exceeded:
                custody.switch_from(self.ao, to=None)
                return None
            # Send hardware commands, slowest to fastest:
##            if emission_filter is not None:
##                self.filter_wheel.move(
##                    tbl_emission_filter_options[emission_filter], block=False)
            if (tbl_height_px is not None or
                tbl_width_px is not None or
                tbl_illumination_time_us is not None):
                self.tbl_camera._disarm()
                self.tbl_camera._set_roi(self.tbl_roi_px) # height_px updated
                self.tbl_camera._set_exposure_time_us(int(
                    self.tbl_illumination_time_us +
                    self.tbl_camera.rolling_time_us))
                self.tbl_camera._arm(self.tbl_camera._num_buffers)
            if tbl_timestamp_mode is not None:
                self.tbl_camera._set_timestamp_mode(tbl_timestamp_mode)
            if (tbl_channels_per_image is not None or
                tbl_power_per_channel is not None or
                tbl_height_px is not None or
                tbl_illumination_time_us is not None or
                tbl_images_per_buffer is not None or
                tbl_camera_preframes is not None):
                for channel in self.tbl_channels_per_image:
                    assert channel in self.illumination_sources
                assert len(self.tbl_power_per_channel) == (
                    len(self.tbl_channels_per_image))
                for i, p in enumerate(self.tbl_power_per_channel):
                    assert 0 <= p <= 100
                assert type(self.tbl_images_per_buffer) is int
                assert self.tbl_images_per_buffer > 0
                assert type(self.tbl_camera_preframes) is int
                self.tbl_camera.num_images = ( # update attribute
                    self.tbl_images + self.tbl_camera_preframes)
                self.tbl_voltages = self._tbl_calculate_voltages()
                self._tbl_update_voltages = True
            # Finalize hardware commands, fastest to slowest:
##            if emission_filter is not None:
##                self.filter_wheel._finish_moving()
            self._tbl_settings_applied = True
            custody.switch_from(self.ao, to=None) # Release camera
        settings_thread = ct.CustodyThread(
            target=settings_task, first_resource=self.tbl_camera).start()
        self.unfinished_tasks.put(settings_thread)
        return settings_thread

    def tbl_acquire(
        self,               # 'tcyx' format
        filename=None,      # None = no save, same string = overwrite
        folder_name=None,   # None = new folder, same string = re-use
        description=None,   # Optional metadata description
        display=True):      # Optional turn off
        def acquire_task(custody):
            custody.switch_from(None, to=self.ao) # get ao
            if not self._tbl_settings_applied:
                if self.print_warnings:
                    print("\n%s: ***WARNING***: settings not applied"%self.name)
                    print("%s: -> please apply legal tbl settings"%self.name)
                    print("%s: (all arguments must be specified at least once)")
                custody.switch_from(self.ao, to=None)
                return
            if self._epi_enabled:
                self._switch_microscopes(epi_enabled=False)
            # must write and play each time with the ni_PCI_6733 card/adaptor:
            if self._tbl_update_voltages: # update if needed
                write_voltages_thread = ct.ResultThread(
                    target=self.ao._write_voltages,
                    args=(self.tbl_voltages,)).start()
            if filename is not None:
                prepare_to_save_thread = ct.ResultThread(
                    target=self._tbl_prepare_to_save,
                    args=(filename, folder_name, description, display)).start()
            # We have custody of the camera so attribute access is safe:
            im   = self.tbl_images_per_buffer
            ch   = len(self.tbl_channels_per_image)
            h_px = self.tbl_height_px
            w_px = self.tbl_width_px
            ti   = self.tbl_images + self.tbl_camera_preframes
            data_buffer = self._tbl_get_data_buffer((ti, h_px, w_px), 'uint16')
            if self._tbl_update_voltages:
                write_voltages_thread.get_result()
                self._tbl_update_voltages = False
            # camera.record_to_memory() blocks, so we use a thread:
            camera_thread = ct.ResultThread(
                target=self.tbl_camera.record_to_memory,
                kwargs={'allocated_memory': data_buffer,
                        'software_trigger': False},).start()
            # Race condition: the camera starts with (typically 16) single
            # frame buffers, which are filled by triggers from
            # ao.play_voltages(). The camera_thread empties them, hopefully
            # fast enough that we never run out. So far, the camera_thread
            # seems to both start on time, and keep up reliably once it starts,
            # but this could be fragile. The camera thread (effectively)
            # acquires shared memory as it writes to the allocated buffer.
            # On this machine the memory acquisition is faster than the camera
            # (~4GB/s vs ~1GB/s) but this could also be fragile if another
            # process interferes.
            self.ao.play_voltages(block=False)
            camera_thread.get_result()
            # Acquisition is 3D, but display and filesaving are 4D:
            data_buffer = data_buffer[ # ditch preframes
                self.tbl_camera_preframes:, :, :].reshape(im, ch, h_px, w_px)
            if display:
                custody.switch_from(self.ao, to=self.display)
                if self.tbl_timestamp_mode == "binary+ASCII":
                    self.display.show_tbl_image(data_buffer[:,:,8:,:])
                else:
                    self.display.show_tbl_image(data_buffer)
                custody.switch_from(self.display, to=None)
            else:
                custody.switch_from(self.ao, to=None)
            if filename is not None:
                data_path = prepare_to_save_thread.get_result()
                if self.verbose:
                    print("%s: saving '%s'"%(self.name, data_path))
                # TODO: consider puting FileSaving in a SubProcess
                imwrite(data_path, data_buffer[:,np.newaxis,:,:,:], imagej=True)
                if self.verbose:
                    print("%s: done saving."%self.name)
            self._tbl_release_data_buffer(data_buffer)
            del data_buffer
        acquire_thread = ct.CustodyThread(
            target=acquire_task, first_resource=self.ao).start()
        self.unfinished_tasks.put(acquire_thread)
        return acquire_thread

    def finish_all_tasks(self):
        collected_tasks = []
        while True:
            try:
                th = self.unfinished_tasks.get_nowait()
            except queue.Empty:
                break
            th.get_result()
            collected_tasks.append(th)
        return collected_tasks

    def close(self):
        if self.verbose: print("%s: closing..."%self.name)
        self.finish_all_tasks()
##        self.filter_wheel.close()
        self.epi_camera.close()
        self.tbl_camera.close()
##        self.laser_box.close()
        self.display.close()
        self.ao.close()
        if self.verbose: print("%s: done closing."%self.name)

class _CustomNapariDisplay:
    def __init__(self, auto_contrast=False):
        self.auto_contrast = auto_contrast
        self.viewer = napari.Viewer()

    def _legalize_slider(self, image):
        for ax in range(len(image.shape) - 2): # slider axes other than X, Y
            # if the current viewer slider steps > corresponding image shape:
            if self.viewer.dims.nsteps[ax] > image.shape[ax]:
                # set the slider position to the max legal value:
                self.viewer.dims.set_point(ax, image.shape[ax] - 1)

    def _reset_contrast(self, image): # 4D image min to max
        for layer in self.viewer.layers: # image, grid, tile
            layer.contrast_limits = (image.min(), image.max())

    def show_epi_image(self, epi_image):
        self._legalize_slider(epi_image)
        if self.auto_contrast:
            self._reset_contrast(epi_image)
        if not hasattr(self, 'epi_image'):
            self.epi_image = self.viewer.add_image(epi_image)
        else:
            self.epi_image.data = epi_image

    def show_tbl_image(self, tbl_image):
        self._legalize_slider(tbl_image)
        if self.auto_contrast:
            self._reset_contrast(tbl_image)
        if not hasattr(self, 'tbl_image'):
            self.tbl_image = self.viewer.add_image(tbl_image)
        else:
            self.tbl_image.data = tbl_image

    def close(self):
        self.viewer.close()

if __name__ == '__main__':
    t0 = time.perf_counter()

    # Create scope object:
    scope = Microscope(max_allocated_bytes=10e9, ao_rate=1e5)
    
    scope.epi_apply_settings(       # Mandatory call
        epi_channels_per_image=("490_LED",),
        epi_power_per_channel=(15,),
        epi_illumination_time_us=1000,
        epi_height_px=2048,
        epi_width_px=2048,
        epi_images_per_buffer=1,
        )#.get_result()
    scope.tbl_apply_settings(       # Mandatory call
        tbl_channels_per_image=("488",),
        tbl_power_per_channel=(15,),
        tbl_illumination_time_us=1000,
        tbl_height_px=2048,
        tbl_width_px=2048,
        tbl_images_per_buffer=1,
        )#.get_result()

    # Acquire:
    epi_folder_label = 'epi_test_data'
    dt = datetime.strftime(datetime.now(),'%Y-%m-%d_%H-%M-%S_000_')
    epi_folder_name = dt + epi_folder_label

    tbl_folder_label = 'tbl_test_data'
    dt = datetime.strftime(datetime.now(),'%Y-%m-%d_%H-%M-%S_000_')
    tbl_folder_name = dt + tbl_folder_label
    for i in range(2):
        scope.epi_acquire(
            filename='%06i.tif'%i,
            folder_name=epi_folder_name,
            description='something...',
            display=True,
            )
        scope.tbl_acquire(
            filename='%06i.tif'%i,
            folder_name=tbl_folder_name,
            description='something...',
            display=True,
            )

    scope.close()

    t1 = time.perf_counter()
    print('time_s', t1 - t0) # ~ 6s
