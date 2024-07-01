# Imports from the python standard library:
import os
import time
import tkinter as tk
from datetime import datetime
from idlelib.tooltip import Hovertip
from tkinter import filedialog
from tkinter import font

# Third party imports, installable via pip:
import numpy as np
from tifffile import imread, imwrite

# Our code, one .py file per module, copy files to your local directory:
import tripsy_microscope as tbl
import tkinter_compound_widgets as tkcw # github.com/amsikking/tkinter

class GuiMicroscope:
    def __init__(self, init_microscope=True): # set False for GUI design...
        self.init_microscope = init_microscope
        self.root = tk.Tk()
        self.root.title('Tripsy Microscope GUI')
        # adjust font size and delay:
        size = 10 # default = 9
        font.nametofont("TkDefaultFont").configure(size=size)
        font.nametofont("TkFixedFont").configure(size=size)
        font.nametofont("TkTextFont").configure(size=size)
        ## epi:
        epi_frame = tk.LabelFrame(self.root, text='EPI MICROSCOPE', bd=6)
        epi_frame.grid(row=0, column=0, padx=5, pady=5, sticky='n')
        epi_frame_tip = Hovertip(epi_frame, "tip...")
        # -> hardware GUI's:
        self.epi_init_led(epi_frame)
        self.epi_init_dichroic_mirror(epi_frame)
        self.epi_init_filter(epi_frame)
        self.epi_init_camera(epi_frame)
        # -> microscope GUI's:
        self.epi_init_settings(epi_frame)           # settings from GUI
        self.epi_init_settings_output(epi_frame)    # output from settings
        self.epi_init_acquire(epi_frame)            # microscope methods
        ## tbl:
        tbl_frame = tk.LabelFrame(self.root, text='TUMBLE MICROSCOPE', bd=6)
        tbl_frame.grid(row=0, column=1, padx=5, pady=5, sticky='n')
        tbl_frame_tip = Hovertip(tbl_frame, "tip...")
        # -> hardware GUI's:
        self.tbl_init_lasers(tbl_frame)
        self.tbl_init_dichroic_mirror(tbl_frame)
        self.tbl_init_filter(tbl_frame)
        self.tbl_init_camera(tbl_frame)
        # -> microscope GUI's:
        self.tbl_init_settings(tbl_frame)           # settings from GUI
        self.tbl_init_settings_output(tbl_frame)    # output from settings
        self.tbl_init_acquire(tbl_frame)            # microscope methods
        # exit and running modes:
        self.init_exit()            # exit the GUI
        self.init_running_mode()    # toggles between different modes
        # optionally initialize microscope:
        if init_microscope:
            self.max_allocated_bytes = 10e9
            self.scope = tbl.Microscope(
                max_allocated_bytes=self.max_allocated_bytes,
                ao_rate=1e5,
                print_warnings=False)
            self.epi_max_bytes_per_buffer = self.scope.epi_max_bytes_per_buffer
            self.tbl_max_bytes_per_buffer = self.scope.epi_max_bytes_per_buffer
            # configure any hardware preferences:
            # (place holder)
            # make mandatory call to 'apply_settings':
            ## epi:
            self.scope.epi_apply_settings(
                epi_channels_per_image   = ('490_LED',),
                epi_power_per_channel    = (self.power_490.value.get(),),
                epi_illumination_time_us = (
                    self.epi_illumination_time_us.value.get()),
                epi_height_px            = self.epi_height_px.value.get(),
                epi_width_px             = self.epi_width_px.value.get(),
                epi_images_per_buffer    = (
                    self.epi_images_per_buffer.value.get()),
                ).get_result() # finish
            ## tbl:
            self.scope.tbl_apply_settings(
                tbl_channels_per_image   = ('490_LED',),
                tbl_power_per_channel    = (self.power_490.value.get(),),
                tbl_illumination_time_us = (
                    self.tbl_illumination_time_us.value.get()),
                tbl_height_px            = self.tbl_height_px.value.get(),
                tbl_width_px             = self.tbl_width_px.value.get(),
                tbl_images_per_buffer    = (
                    self.tbl_images_per_buffer.value.get()),
                ).get_result() # finish
            # check microscope periodically:
            def _run_check_microscope():
                ## epi:
                # update attributes:
                self.scope.epi_apply_settings().get_result()
                # check memory:
                self.epi_data_bytes.set(
                    self.scope.epi_bytes_per_data_buffer)
                self.epi_data_buffer_exceeded.set(
                    self.scope.epi_data_buffer_exceeded)
                self.epi_total_bytes.set(
                    self.scope.epi_total_bytes)
                self.epi_total_bytes_exceeded.set(
                    self.scope.epi_total_bytes_exceeded)
                # calculate voltages:
                self.epi_buffer_time_s.set(self.scope.epi_buffer_time_s)
                self.epi_frames_per_s.set(self.scope.epi_frames_per_s)
                ## tbl:
                # update attributes:
                self.scope.tbl_apply_settings().get_result()
                # check memory:
                self.tbl_data_bytes.set(
                    self.scope.tbl_bytes_per_data_buffer)
                self.tbl_data_buffer_exceeded.set(
                    self.scope.tbl_data_buffer_exceeded)
                self.tbl_total_bytes.set(
                    self.scope.tbl_total_bytes)
                self.tbl_total_bytes_exceeded.set(
                    self.scope.tbl_total_bytes_exceeded)
                # calculate voltages:
                self.tbl_buffer_time_s.set(self.scope.tbl_buffer_time_s)
                self.tbl_frames_per_s.set(self.scope.tbl_frames_per_s)
                # update GUI highlight:
                bg_color = '#FFCCCB'
                if self.scope._epi_enabled:
                    self.epi_inner_frame.configure(bg=bg_color)
                    self.tbl_inner_frame.configure(bg='SystemButtonFace')
                else:
                    self.epi_inner_frame.configure(bg='SystemButtonFace')
                    self.tbl_inner_frame.configure(bg=bg_color)
                self.root.after(int(1e3/10), _run_check_microscope) # 30fps
                return None
            _run_check_microscope()
            # make session folder:
            dt = datetime.strftime(datetime.now(),'%Y-%m-%d_%H-%M-%S_')
            self.session_folder = dt + 'tripsy_gui_session\\'
            os.makedirs(self.session_folder)
            # snap:
            self.last_acquire_task = self.scope.epi_acquire()
        # start event loop:
        self.root.mainloop() # blocks here until 'QUIT'
        self.root.destroy()

    def epi_init_led(self, epi_frame):
        frame = tk.LabelFrame(epi_frame, text='LED', bd=6)
        frame.grid(row=0, column=0, rowspan=1, padx=5, pady=5, sticky='n')
        frame_tip = Hovertip(frame, "tip...")
        # 490:
        self.power_490 = tkcw.CheckboxSliderSpinbox(
            frame,
            label='490nm (%)',
            color='blue',
            slider_length=150,
            default_value=5,
            width=5)
        self.power_490.checkbox_value.trace_add(
            'write', self._epi_apply_channel_settings)
        self.power_490.value.trace_add(
            'write', self._epi_apply_channel_settings)
        return None

    def _epi_apply_channel_settings(self, var, index, mode):
        # var, index, mode are passed from .trace_add but not used
        channels_per_image, power_per_channel = [], []
        if self.power_490.checkbox_value.get():
            channels_per_image.append('490_LED')
            power_per_channel.append(self.power_490.value.get())
        if len(channels_per_image) > 0: # at least 1 channel selected
            self.scope.epi_apply_settings(
                epi_channels_per_image=channels_per_image,
                epi_power_per_channel=power_per_channel)
        return None

    def epi_init_dichroic_mirror(self, epi_frame):
        frame = tk.LabelFrame(epi_frame, text='DICHROIC MIRROR', bd=6)
        frame.grid(row=1, column=0, padx=5, pady=5, sticky='n')
        frame_tip = Hovertip(frame, "tip...")
        inner_frame = tk.LabelFrame(frame, text='fixed')
        inner_frame.grid(row=0, column=0, padx=10, pady=10)
        epi_dichroic_mirror_options = tuple(
            tbl.epi_dichroic_mirror_options.keys())
        self.epi_dichroic_mirror = tk.StringVar()
        self.epi_dichroic_mirror.set(epi_dichroic_mirror_options[0]) # default
        option_menu = tk.OptionMenu(
            inner_frame,
            self.epi_dichroic_mirror,
            *epi_dichroic_mirror_options)
        option_menu.config(width=38, height=2) # match to led
        option_menu.grid(row=0, column=0, padx=10, pady=10)
        return None

    def epi_init_filter(self, epi_frame):
        frame = tk.LabelFrame(epi_frame, text='EMISSION FILTER', bd=6)
        frame.grid(row=2, column=0, padx=5, pady=5, sticky='n')
        frame_tip = Hovertip(frame, "tip...")
        inner_frame = tk.LabelFrame(frame, text='fixed')
        inner_frame.grid(row=0, column=0, padx=10, pady=10)
        epi_emission_filter_options = tuple(
            tbl.epi_emission_filter_options.keys())
        self.epi_emission_filter = tk.StringVar()
        self.epi_emission_filter.set(epi_emission_filter_options[0]) # default
        option_menu = tk.OptionMenu(
            inner_frame,
            self.epi_emission_filter,
            *epi_emission_filter_options)
        option_menu.config(width=38, height=2) # match to led
        option_menu.grid(row=0, column=0, padx=10, pady=10)
        return None

    def epi_init_camera(self, epi_frame):
        frame = tk.LabelFrame(epi_frame, text='CAMERA', bd=6)
        frame.grid(row=0, column=1, rowspan=4, columnspan=2,
                   padx=5, pady=5, sticky='n')
        # illumination_time_us:
        self.epi_illumination_time_us = tkcw.CheckboxSliderSpinbox(
            frame,
            label='illumination time (us)',
            checkbox_enabled=False,
            slider_enabled=False,
            min_value=100,
            max_value=1000000,
            default_value=10000,
            columnspan=2,
            row=0,
            width=10,
            sticky='w')
        self.epi_illumination_time_us.value.trace_add(
            'write',
            lambda var, index, mode: self.scope.epi_apply_settings(
                epi_illumination_time_us=(
                    self.epi_illumination_time_us.value.get())))
        epi_illumination_time_us_tip = Hovertip(
            self.epi_illumination_time_us, "tip...")
        # height_px:
        self.epi_height_px = tkcw.CheckboxSliderSpinbox(
            frame,
            label='height pixels',
            orient='vertical',
            checkbox_enabled=False,
            slider_length=170,
            tickinterval=4,
            slider_flipped=True,
            min_value=10,
            max_value=2048,
            default_value=2048,
            row=1,
            width=5)
        self.epi_height_px.value.trace_add(
            'write',
            lambda var, index, mode: self.scope.epi_apply_settings(
                epi_height_px=self.epi_height_px.value.get()))
        epi_height_px_tip = Hovertip(self.epi_height_px, "tip...")
        # width_px:
        self.epi_width_px = tkcw.CheckboxSliderSpinbox(
            frame,
            label='width pixels',
            checkbox_enabled=False,
            slider_length=180,
            tickinterval=4,
            min_value=64,
            max_value=2048,
            default_value=2048,
            row=2,
            column=1,
            sticky='s',
            width=5)
        self.epi_width_px.value.trace_add(
            'write',
            lambda var, index, mode: self.scope.epi_apply_settings(
                epi_width_px=self.epi_width_px.value.get()))
        epi_width_px_tip = Hovertip(self.epi_width_px, "tip...")
        # ROI display:
        tkcw.CanvasRectangleSliderTrace2D(
            frame,
            self.epi_width_px,
            self.epi_height_px,
            row=1,
            column=1,
            fill='yellow')
        return None

    def _epi_snap_and_display(self):
        if self.epi_images_per_buffer.value.get() != 1:
            self.epi_images_per_buffer.update_and_validate(1)
        self.last_acquire_task.get_result() # don't accumulate
        self.last_acquire_task = self.scope.epi_acquire()
        return None

    def _epi_get_folder_name(self):
        dt = datetime.strftime(datetime.now(),'%Y-%m-%d_%H-%M-%S_')
        folder_index = 0
        folder_name = (
            self.session_folder + dt +
            '%03i_'%folder_index + self.epi_label_textbox.text)
        while os.path.exists(folder_name): # check before overwriting
            folder_index +=1
            folder_name = (
                self.session_folder + dt +
                '%03i_'%folder_index + self.label_textbox.text)
        return folder_name

    def epi_init_settings(self, epi_frame):
        frame = tk.LabelFrame(epi_frame, text='SETTINGS (misc)', bd=6)
        frame.grid(row=4, column=1, rowspan=5, padx=5, pady=5, sticky='n')
        button_width, button_height = 25, 1
        spinbox_width = 17
        # label textbox:
        self.epi_label_textbox = tkcw.Textbox(
            frame,
            label='Folder label',
            default_text='epi',
            row=1,
            width=spinbox_width,
            height=1,
            columnspan=2)
        epi_label_textbox_tip = Hovertip(self.epi_label_textbox, "tip...")
        # description textbox:
        self.epi_description_textbox = tkcw.Textbox(
            frame,
            label='Description',
            default_text='what are you doing?',
            row=2,
            width=spinbox_width,
            height=3,
            columnspan=2)
        epi_description_textbox_tip = Hovertip(
            self.epi_description_textbox, "tip...")       
        # images spinbox:
        self.epi_images_per_buffer = tkcw.CheckboxSliderSpinbox(
            frame,
            label='Images per acquire',
            checkbox_enabled=False,
            slider_enabled=False,
            min_value=1,
            max_value=1e3,
            default_value=1,
            row=3,
            width=spinbox_width,
            columnspan=2)
        self.epi_images_per_buffer.value.trace_add(
            'write',
            lambda var, index, mode: self.scope.epi_apply_settings(
                epi_images_per_buffer=self.epi_images_per_buffer.value.get()))
        epi_images_per_buffer_tip = Hovertip(
            self.epi_images_per_buffer, "tip...")
        # acquire number spinbox:
        self.epi_acquire_number = tkcw.CheckboxSliderSpinbox(
            frame,
            label='Acquire number',
            checkbox_enabled=False,
            slider_enabled=False,
            min_value=1,
            max_value=1e6,
            default_value=1,
            row=9,
            width=spinbox_width,
            columnspan=2)
        epi_acquire_number_spinbox_tip = Hovertip(
            self.epi_acquire_number, "tip...")
        # delay spinbox:
        self.epi_delay_s = tkcw.CheckboxSliderSpinbox(
            frame,
            label='Inter-acquire delay (s) >=',
            checkbox_enabled=False,
            slider_enabled=False,
            min_value=0,
            max_value=3600,
            default_value=0,
            row=10,
            width=spinbox_width,
            columnspan=2)
        epi_delay_spinbox_tip = Hovertip(self.epi_delay_s, "tip")        
        return None

    def epi_init_settings_output(self, epi_frame):
        frame = tk.LabelFrame(epi_frame, text='SETTINGS OUTPUT', bd=6)
        frame.grid(row=4, column=2, rowspan=3, padx=5, pady=5, sticky='s')
        button_width, button_height = 25, 2
        spinbox_width = 17
        # frames per second textbox:
        self.epi_frames_per_s = tk.DoubleVar()
        epi_frames_per_s_textbox = tkcw.Textbox(
            frame,
            label='Frames per second',
            default_text='None',
            row=0,
            width=spinbox_width,
            height=1)
        def _update_epi_frames_per_s():            
            text = '%0.3f'%self.epi_frames_per_s.get()
            epi_frames_per_s_textbox.textbox.delete('1.0', 'end')
            epi_frames_per_s_textbox.textbox.insert('1.0', text)
            return None
        self.epi_frames_per_s.trace_add(
            'write',
            lambda var, index, mode: _update_epi_frames_per_s())
        epi_frames_per_s_textbox_tip = Hovertip(
            epi_frames_per_s_textbox, "tip...")
        # data memory textbox:
        self.epi_data_bytes = tk.IntVar()
        self.epi_data_buffer_exceeded = tk.BooleanVar()
        epi_data_memory_textbox = tkcw.Textbox(
            frame,
            label='Data memory (GB)',
            default_text='None',
            row=1,
            width=spinbox_width,
            height=1)
        epi_data_memory_textbox.textbox.tag_add('color', '1.0', 'end')
        def _update_epi_data_memory():
            data_memory_gb = 1e-9 * self.epi_data_bytes.get()
            max_memory_gb = 1e-9 * self.epi_max_bytes_per_buffer
            memory_pct = 100 * data_memory_gb / max_memory_gb
            text = '%0.3f (%0.2f%% max)'%(data_memory_gb, memory_pct)
            epi_data_memory_textbox.textbox.delete('1.0', 'end')
            bg = 'white'
            if self.epi_data_buffer_exceeded.get(): bg = 'red'
            epi_data_memory_textbox.textbox.tag_config('color', background=bg)
            epi_data_memory_textbox.textbox.insert('1.0', text, 'color')
            return None
        self.epi_data_bytes.trace_add(
            'write',
            lambda var, index, mode: _update_epi_data_memory())
        epi_data_memory_textbox_tip = Hovertip(epi_data_memory_textbox, "tip")
        # total memory textbox:
        self.epi_total_bytes = tk.IntVar()
        self.epi_total_bytes_exceeded = tk.BooleanVar()
        epi_total_memory_textbox = tkcw.Textbox(
            frame,
            label='Total memory (GB)',
            default_text='None',
            row=2,
            width=spinbox_width,
            height=1)
        epi_total_memory_textbox.textbox.tag_add('color', '1.0', 'end')
        def _update_epi_total_memory():
            total_memory_gb = 1e-9 * self.epi_total_bytes.get()
            max_memory_gb = 1e-9 * self.max_allocated_bytes
            memory_pct = 100 * total_memory_gb / max_memory_gb
            text = '%0.3f (%0.2f%% max)'%(total_memory_gb, memory_pct)
            epi_total_memory_textbox.textbox.delete('1.0', 'end')
            bg = 'white'
            if self.epi_total_bytes_exceeded.get(): bg = 'red'
            epi_total_memory_textbox.textbox.tag_config('color', background=bg)
            epi_total_memory_textbox.textbox.insert('1.0', text, 'color')
            return None
        self.epi_total_bytes.trace_add(
            'write',
            lambda var, index, mode: _update_epi_total_memory())
        total_epi_memory_textbox_tip = Hovertip(
            epi_total_memory_textbox, "tip...")
        # total storage textbox:
        epi_total_storage_textbox = tkcw.Textbox(
            frame,
            label='Total storage (GB)',
            default_text='None',
            row=3,
            width=spinbox_width,
            height=1)
        def _update_epi_total_storage():
            acquires = self.epi_acquire_number.value.get()
            data_gb = 1e-9 * self.epi_data_bytes.get()
            total_storage_gb = data_gb * acquires
            text = '%0.3f'%total_storage_gb
            epi_total_storage_textbox.textbox.delete('1.0', 'end')
            epi_total_storage_textbox.textbox.insert('1.0', text)
            return None
        self.epi_total_bytes.trace_add(
            'write',
            lambda var, index, mode: _update_epi_total_storage())
        epi_total_storage_textbox_tip = Hovertip(
            epi_total_storage_textbox, "tip...")
        # min time textbox:
        self.epi_buffer_time_s = tk.DoubleVar()
        epi_min_time_textbox = tkcw.Textbox(
            frame,
            label='Minimum acquire time (s)',
            default_text='None',
            row=4,
            width=spinbox_width,
            height=1)
        def _update_epi_min_time():
            acquires = self.epi_acquire_number.value.get()
            min_acquire_time_s = self.epi_buffer_time_s.get()
            min_total_time_s = min_acquire_time_s * acquires
            delay_s = self.epi_delay_s.value.get()
            if delay_s > min_acquire_time_s:
                min_total_time_s = ( # start -> n-1 delays -> final acquire
                    delay_s * (acquires - 1) + min_acquire_time_s)
            text = '%0.6f (%0.0f min)'%(
                min_total_time_s, (min_total_time_s / 60))
            epi_min_time_textbox.textbox.delete('1.0', 'end')
            epi_min_time_textbox.textbox.insert('1.0', text)
            return None
        self.epi_buffer_time_s.trace_add(
            'write',
            lambda var, index, mode: _update_epi_min_time())
        epi_min_time_textbox_tip = Hovertip(epi_min_time_textbox, "tip...")
        return None

    def epi_init_acquire(self, epi_frame):
        frame = tk.LabelFrame(
            epi_frame, text='ACQUIRE', font=('Segoe UI', '10', 'bold'), bd=6)
        frame.grid(row=0, column=3, rowspan=4, padx=5, pady=5, sticky='n')
        frame.bind('<Enter>', lambda event: frame.focus_set()) # force update
        self.epi_inner_frame = tk.LabelFrame(frame)
        self.epi_inner_frame.grid()
        button_width, button_height = 20, 2
        bold_width_adjust = -3
        spinbox_width = 20
        # snap:
        snap_button = tk.Button(
            self.epi_inner_frame,
            text="Snap",
            command=self._epi_snap_and_display,
            font=('Segoe UI', '10', 'bold'),
            width=button_width + bold_width_adjust,
            height=button_height)
        snap_button.grid(row=0, column=0, padx=10, pady=10)
        snap_button_tip = Hovertip(snap_button, "tip...")
        # live mode:
        def _live_mode():
            if self.epi_running_live_mode.get():
                self._set_running_mode('epi_live_mode')
            else:
                self._set_running_mode('None')
            def _run_live_mode():
                if self.epi_running_live_mode.get():
                    if not self.last_acquire_task.is_alive():
                        self._epi_snap_and_display()
                    self.root.after(int(1e3/30), _run_live_mode) # 30 fps
                return None
            _run_live_mode()
            return None
        self.epi_running_live_mode = tk.BooleanVar()
        live_mode_button = tk.Checkbutton(
            self.epi_inner_frame,
            text='Live mode (On/Off)',
            variable=self.epi_running_live_mode,
            command=_live_mode,
            indicatoron=0,
            font=('Segoe UI', '10', 'italic'),
            width=button_width,
            height=button_height)
        live_mode_button.grid(row=1, column=0, padx=10, pady=10)
        live_mode_button_tip = Hovertip(live_mode_button, "tip...")
        # save image:
        def _save_image():
            if self.epi_images_per_buffer.value.get() != 1:
                self.epi_images_per_buffer.update_and_validate(1)
            folder_name = self._epi_get_folder_name() + '_snap'
            self.last_acquire_task.get_result() # don't accumulate acquires
            self.scope.epi_acquire(
                filename='snap.tif',
                folder_name=folder_name,
                description=self.epi_description_textbox.text)
            return None
        save_image_button = tk.Button(
            self.epi_inner_frame,
            text="Save image",
            command=_save_image,
            font=('Segoe UI', '10', 'bold'),
            fg='blue',
            width=button_width + bold_width_adjust,
            height=button_height)
        save_image_button.grid(row=3, column=0, padx=10, pady=10)
        save_image_tip = Hovertip(save_image_button, "tip...")
        # run acquire:
        def _acquire():
            print('\nAcquire -> started')
            self._set_running_mode('epi_acquire')
            self.folder_name = self._epi_get_folder_name() + '_acquire'
            self.delay_saved = False
            self.acquire_count = 0
            def _run_acquire():
                if not self.epi_running_acquire.get(): # check for cancel
                    return None
                # don't launch all tasks: either wait 1 buffer time or delay:
                wait_ms = int(round(1e3 * self.scope.epi_buffer_time_s))
                self.scope.epi_acquire(
                    filename='%06i.tif'%self.acquire_count,
                    folder_name=self.folder_name,
                    description=self.epi_description_textbox.text)
                self.acquire_count += 1
                if self.epi_delay_s.value.get() > self.scope.epi_buffer_time_s:
                    wait_ms = int(round(1e3 * self.epi_delay_s.value.get()))                    
                # record gui delay:
                if (not self.delay_saved and os.path.exists(
                    self.folder_name)):
                    with open(self.folder_name + '\\'  "gui_delay_s.txt",
                              "w") as file:
                        file.write(self.folder_name + '\n')
                        file.write(
                            'gui_delay_s: %i'%self.epi_delay_s.value.get() +
                            '\n')
                        self.delay_saved = True
                # check acquire count before re-run:
                if self.acquire_count < self.epi_acquire_number.value.get():
                    self.root.after(wait_ms, _run_acquire)
                else:
                    self.scope.finish_all_tasks()
                    self._set_running_mode('None')
                    print('Acquire -> finished\n')
                return None
            _run_acquire()
            return None
        self.epi_running_acquire = tk.BooleanVar()
        acquire_button = tk.Checkbutton(
            self.epi_inner_frame,
            text="Run acquire",
            variable=self.epi_running_acquire,
            command=_acquire,
            indicatoron=0,
            font=('Segoe UI', '10', 'bold'),
            fg='red',
            width=button_width + bold_width_adjust,
            height=button_height)
        acquire_button.grid(row=4, column=0, padx=10, pady=10)
        acquire_button_tip = Hovertip(acquire_button, "tip...")
        return None

    def tbl_init_lasers(self, tbl_frame):
        frame = tk.LabelFrame(tbl_frame, text='LASERS', bd=6)
        frame.grid(row=0, column=0, rowspan=5, padx=5, pady=5, sticky='n')
        frame_tip = Hovertip(frame, "tip...")
        # 488:
        self.power_488 = tkcw.CheckboxSliderSpinbox(
            frame,
            label='488nm (%)',
            color='blue',
            slider_length=150,
            default_value=5,
            row=0,
            width=5)
        self.power_488.checkbox_value.trace_add(
            'write', self._tbl_apply_channel_settings)
        self.power_488.value.trace_add(
            'write', self._tbl_apply_channel_settings)
        # 785:
        self.power_785 = tkcw.CheckboxSliderSpinbox(
            frame,
            label='785nm (%)',
            color='red',
            slider_length=150,
            default_value=5,
            row=1,
            width=5)
        self.power_785.checkbox_value.trace_add(
            'write', self._tbl_apply_channel_settings)
        self.power_785.value.trace_add(
            'write', self._tbl_apply_channel_settings)
        # 830:
        self.power_830 = tkcw.CheckboxSliderSpinbox(
            frame,
            label='830nm (%)',
            color='red',
            slider_length=150,
            default_value=5,
            row=2,
            width=5)
        self.power_830.checkbox_value.trace_add(
            'write', self._tbl_apply_channel_settings)
        self.power_830.value.trace_add(
            'write', self._tbl_apply_channel_settings)
        # 915:
        self.power_915 = tkcw.CheckboxSliderSpinbox(
            frame,
            label='915nm (%)',
            color='red',
            slider_length=150,
            default_value=5,
            row=3,
            width=5)
        self.power_915.checkbox_value.trace_add(
            'write', self._tbl_apply_channel_settings)
        self.power_915.value.trace_add(
            'write', self._tbl_apply_channel_settings)
        # 940:
        self.power_940 = tkcw.CheckboxSliderSpinbox(
            frame,
            label='940nm (%)',
            color='red',
            slider_length=150,
            default_value=5,
            row=4,
            width=5)
        self.power_940.checkbox_value.trace_add(
            'write', self._tbl_apply_channel_settings)
        self.power_940.value.trace_add(
            'write', self._tbl_apply_channel_settings)
        return None

    def _tbl_apply_channel_settings(self, var, index, mode):
        # var, index, mode are passed from .trace_add but not used
        channels_per_image, power_per_channel = [], []
        if self.power_488.checkbox_value.get():
            channels_per_image.append('488')
            power_per_channel.append(self.power_488.value.get())
        if self.power_785.checkbox_value.get():
            channels_per_image.append('785')
            power_per_channel.append(self.power_785.value.get())
        if self.power_830.checkbox_value.get():
            channels_per_image.append('830')
            power_per_channel.append(self.power_830.value.get())
        if self.power_915.checkbox_value.get():
            channels_per_image.append('915')
            power_per_channel.append(self.power_915.value.get())
        if self.power_940.checkbox_value.get():
            channels_per_image.append('940')
            power_per_channel.append(self.power_940.value.get())
        if len(channels_per_image) > 0: # at least 1 channel selected
            self.scope.tbl_apply_settings(
                tbl_channels_per_image=channels_per_image,
                tbl_power_per_channel=power_per_channel)
        return None

    def tbl_init_dichroic_mirror(self, tbl_frame):
        frame = tk.LabelFrame(tbl_frame, text='DICHROIC MIRROR', bd=6)
        frame.grid(row=5, column=0, padx=5, pady=5, sticky='n')
        frame_tip = Hovertip(frame, "tip...")
        inner_frame = tk.LabelFrame(frame, text='fixed')
        inner_frame.grid(row=0, column=0, padx=10, pady=10)
        tbl_dichroic_mirror_options = tuple(
            tbl.tbl_dichroic_mirror_options.keys())
        self.tbl_dichroic_mirror = tk.StringVar()
        self.tbl_dichroic_mirror.set(tbl_dichroic_mirror_options[0]) # default
        option_menu = tk.OptionMenu(
            inner_frame,
            self.tbl_dichroic_mirror,
            *tbl_dichroic_mirror_options)
        option_menu.config(width=38, height=2) # match to led
        option_menu.grid(row=0, column=0, padx=10, pady=10)
        return None

    def tbl_init_filter(self, tbl_frame):
        frame = tk.LabelFrame(tbl_frame, text='EMISSION FILTER', bd=6)
        frame.grid(row=6, column=0, padx=5, pady=5, sticky='n')
        frame_tip = Hovertip(frame, "tip...")
        inner_frame = tk.LabelFrame(frame, text='fixed')
        inner_frame.grid(row=0, column=0, padx=10, pady=10)
        tbl_emission_filter_options = tuple(
            tbl.tbl_emission_filter_options.keys())
        self.tbl_emission_filter = tk.StringVar()
        self.tbl_emission_filter.set(tbl_emission_filter_options[0]) # default
        option_menu = tk.OptionMenu(
            inner_frame,
            self.tbl_emission_filter,
            *tbl_emission_filter_options)
        option_menu.config(width=38, height=2) # match to led
        option_menu.grid(row=0, column=0, padx=10, pady=10)
        return None

    def tbl_init_camera(self, tbl_frame):
        frame = tk.LabelFrame(tbl_frame, text='CAMERA', bd=6)
        frame.grid(row=0, column=1, rowspan=4, columnspan=2,
                   padx=5, pady=5, sticky='n')
        # illumination_time_us:
        self.tbl_illumination_time_us = tkcw.CheckboxSliderSpinbox(
            frame,
            label='illumination time (us)',
            checkbox_enabled=False,
            slider_enabled=False,
            min_value=100,
            max_value=1000000,
            default_value=10000,
            columnspan=2,
            row=0,
            width=10,
            sticky='w')
        self.tbl_illumination_time_us.value.trace_add(
            'write',
            lambda var, index, mode: self.scope.tbl_apply_settings(
                tbl_illumination_time_us=(
                    self.tbl_illumination_time_us.value.get())))
        tbl_illumination_time_us_tip = Hovertip(
            self.tbl_illumination_time_us, "tip...")
        # height_px:
        self.tbl_height_px = tkcw.CheckboxSliderSpinbox(
            frame,
            label='height pixels',
            orient='vertical',
            checkbox_enabled=False,
            slider_length=170,
            tickinterval=4,
            slider_flipped=True,
            min_value=10,
            max_value=2048,
            default_value=2048,
            row=1,
            width=5)
        self.tbl_height_px.value.trace_add(
            'write',
            lambda var, index, mode: self.scope.tbl_apply_settings(
                tbl_height_px=self.tbl_height_px.value.get()))
        tbl_height_px_tip = Hovertip(self.tbl_height_px, "tip...")
        # width_px:
        self.tbl_width_px = tkcw.CheckboxSliderSpinbox(
            frame,
            label='width pixels',
            checkbox_enabled=False,
            slider_length=180,
            tickinterval=4,
            min_value=64,
            max_value=2048,
            default_value=2048,
            row=2,
            column=1,
            sticky='s',
            width=5)
        self.tbl_width_px.value.trace_add(
            'write',
            lambda var, index, mode: self.scope.tbl_apply_settings(
                tbl_width_px=self.tbl_width_px.value.get()))
        tbl_width_px_tip = Hovertip(self.tbl_width_px, "tip...")
        # ROI display:
        tkcw.CanvasRectangleSliderTrace2D(
            frame,
            self.tbl_width_px,
            self.tbl_height_px,
            row=1,
            column=1,
            fill='green')
        return None

    def _tbl_snap_and_display(self):
        if self.tbl_images_per_buffer.value.get() != 1:
            self.tbl_images_per_buffer.update_and_validate(1)
        self.last_acquire_task.get_result() # don't accumulate
        self.last_acquire_task = self.scope.tbl_acquire()
        return None

    def _tbl_get_folder_name(self):
        dt = datetime.strftime(datetime.now(),'%Y-%m-%d_%H-%M-%S_')
        folder_index = 0
        folder_name = (
            self.session_folder + dt +
            '%03i_'%folder_index + self.tbl_label_textbox.text)
        while os.path.exists(folder_name): # check before overwriting
            folder_index +=1
            folder_name = (
                self.session_folder + dt +
                '%03i_'%folder_index + self.label_textbox.text)
        return folder_name

    def tbl_init_settings(self, tbl_frame):
        frame = tk.LabelFrame(tbl_frame, text='SETTINGS (misc)', bd=6)
        frame.grid(row=4, column=1, rowspan=5, padx=5, pady=5, sticky='n')
        button_width, button_height = 25, 1
        spinbox_width = 17
        # label textbox:
        self.tbl_label_textbox = tkcw.Textbox(
            frame,
            label='Folder label',
            default_text='tbl',
            row=1,
            width=spinbox_width,
            height=1,
            columnspan=2)
        tbl_label_textbox_tip = Hovertip(self.tbl_label_textbox, "tip...")
        # description textbox:
        self.tbl_description_textbox = tkcw.Textbox(
            frame,
            label='Description',
            default_text='what are you doing?',
            row=2,
            width=spinbox_width,
            height=3,
            columnspan=2)
        tbl_description_textbox_tip = Hovertip(
            self.tbl_description_textbox, "tip...")       
        # images spinbox:
        self.tbl_images_per_buffer = tkcw.CheckboxSliderSpinbox(
            frame,
            label='Images per acquire',
            checkbox_enabled=False,
            slider_enabled=False,
            min_value=1,
            max_value=1e3,
            default_value=1,
            row=3,
            width=spinbox_width,
            columnspan=2)
        self.tbl_images_per_buffer.value.trace_add(
            'write',
            lambda var, index, mode: self.scope.tbl_apply_settings(
                tbl_images_per_buffer=self.tbl_images_per_buffer.value.get()))
        tbl_images_per_buffer_tip = Hovertip(
            self.tbl_images_per_buffer, "tip...")
        # acquire number spinbox:
        self.tbl_acquire_number = tkcw.CheckboxSliderSpinbox(
            frame,
            label='Acquire number',
            checkbox_enabled=False,
            slider_enabled=False,
            min_value=1,
            max_value=1e6,
            default_value=1,
            row=9,
            width=spinbox_width,
            columnspan=2)
        tbl_acquire_number_spinbox_tip = Hovertip(
            self.tbl_acquire_number, "tip...")
        # delay spinbox:
        self.tbl_delay_s = tkcw.CheckboxSliderSpinbox(
            frame,
            label='Inter-acquire delay (s) >=',
            checkbox_enabled=False,
            slider_enabled=False,
            min_value=0,
            max_value=3600,
            default_value=0,
            row=10,
            width=spinbox_width,
            columnspan=2)
        tbl_delay_spinbox_tip = Hovertip(self.tbl_delay_s, "tip")        
        return None

    def tbl_init_settings_output(self, tbl_frame):
        frame = tk.LabelFrame(tbl_frame, text='SETTINGS OUTPUT', bd=6)
        frame.grid(row=4, column=2, rowspan=3, padx=5, pady=5, sticky='s')
        button_width, button_height = 25, 2
        spinbox_width = 17
        # frames per second textbox:
        self.tbl_frames_per_s = tk.DoubleVar()
        tbl_frames_per_s_textbox = tkcw.Textbox(
            frame,
            label='Frames per second',
            default_text='None',
            row=0,
            width=spinbox_width,
            height=1)
        def _update_tbl_frames_per_s():            
            text = '%0.3f'%self.tbl_frames_per_s.get()
            tbl_frames_per_s_textbox.textbox.delete('1.0', 'end')
            tbl_frames_per_s_textbox.textbox.insert('1.0', text)
            return None
        self.tbl_frames_per_s.trace_add(
            'write',
            lambda var, index, mode: _update_tbl_frames_per_s())
        tbl_frames_per_s_textbox_tip = Hovertip(
            tbl_frames_per_s_textbox, "tip...")
        # data memory textbox:
        self.tbl_data_bytes = tk.IntVar()
        self.tbl_data_buffer_exceeded = tk.BooleanVar()
        tbl_data_memory_textbox = tkcw.Textbox(
            frame,
            label='Data memory (GB)',
            default_text='None',
            row=1,
            width=spinbox_width,
            height=1)
        tbl_data_memory_textbox.textbox.tag_add('color', '1.0', 'end')
        def _update_tbl_data_memory():
            data_memory_gb = 1e-9 * self.tbl_data_bytes.get()
            max_memory_gb = 1e-9 * self.tbl_max_bytes_per_buffer
            memory_pct = 100 * data_memory_gb / max_memory_gb
            text = '%0.3f (%0.2f%% max)'%(data_memory_gb, memory_pct)
            tbl_data_memory_textbox.textbox.delete('1.0', 'end')
            bg = 'white'
            if self.tbl_data_buffer_exceeded.get(): bg = 'red'
            tbl_data_memory_textbox.textbox.tag_config('color', background=bg)
            tbl_data_memory_textbox.textbox.insert('1.0', text, 'color')
            return None
        self.tbl_data_bytes.trace_add(
            'write',
            lambda var, index, mode: _update_tbl_data_memory())
        tbl_data_memory_textbox_tip = Hovertip(tbl_data_memory_textbox, "tip")
        # total memory textbox:
        self.tbl_total_bytes = tk.IntVar()
        self.tbl_total_bytes_exceeded = tk.BooleanVar()
        tbl_total_memory_textbox = tkcw.Textbox(
            frame,
            label='Total memory (GB)',
            default_text='None',
            row=2,
            width=spinbox_width,
            height=1)
        tbl_total_memory_textbox.textbox.tag_add('color', '1.0', 'end')
        def _update_tbl_total_memory():
            total_memory_gb = 1e-9 * self.tbl_total_bytes.get()
            max_memory_gb = 1e-9 * self.max_allocated_bytes
            memory_pct = 100 * total_memory_gb / max_memory_gb
            text = '%0.3f (%0.2f%% max)'%(total_memory_gb, memory_pct)
            tbl_total_memory_textbox.textbox.delete('1.0', 'end')
            bg = 'white'
            if self.tbl_total_bytes_exceeded.get(): bg = 'red'
            tbl_total_memory_textbox.textbox.tag_config('color', background=bg)
            tbl_total_memory_textbox.textbox.insert('1.0', text, 'color')
            return None
        self.tbl_total_bytes.trace_add(
            'write',
            lambda var, index, mode: _update_tbl_total_memory())
        total_tbl_memory_textbox_tip = Hovertip(
            tbl_total_memory_textbox, "tip...")
        # total storage textbox:
        tbl_total_storage_textbox = tkcw.Textbox(
            frame,
            label='Total storage (GB)',
            default_text='None',
            row=3,
            width=spinbox_width,
            height=1)
        def _update_tbl_total_storage():
            acquires = self.tbl_acquire_number.value.get()
            data_gb = 1e-9 * self.tbl_data_bytes.get()
            total_storage_gb = data_gb * acquires
            text = '%0.3f'%total_storage_gb
            tbl_total_storage_textbox.textbox.delete('1.0', 'end')
            tbl_total_storage_textbox.textbox.insert('1.0', text)
            return None
        self.tbl_total_bytes.trace_add(
            'write',
            lambda var, index, mode: _update_tbl_total_storage())
        tbl_total_storage_textbox_tip = Hovertip(
            tbl_total_storage_textbox, "tip...")
        # min time textbox:
        self.tbl_buffer_time_s = tk.DoubleVar()
        tbl_min_time_textbox = tkcw.Textbox(
            frame,
            label='Minimum acquire time (s)',
            default_text='None',
            row=4,
            width=spinbox_width,
            height=1)
        def _update_tbl_min_time():
            acquires = self.tbl_acquire_number.value.get()
            min_acquire_time_s = self.tbl_buffer_time_s.get()
            min_total_time_s = min_acquire_time_s * acquires
            delay_s = self.tbl_delay_s.value.get()
            if delay_s > min_acquire_time_s:
                min_total_time_s = ( # start -> n-1 delays -> final acquire
                    delay_s * (acquires - 1) + min_acquire_time_s)
            text = '%0.6f (%0.0f min)'%(
                min_total_time_s, (min_total_time_s / 60))
            tbl_min_time_textbox.textbox.delete('1.0', 'end')
            tbl_min_time_textbox.textbox.insert('1.0', text)
            return None
        self.tbl_buffer_time_s.trace_add(
            'write',
            lambda var, index, mode: _update_tbl_min_time())
        tbl_min_time_textbox_tip = Hovertip(tbl_min_time_textbox, "tip...")
        return None

    def tbl_init_acquire(self, tbl_frame):
        frame = tk.LabelFrame(
            tbl_frame, text='ACQUIRE', font=('Segoe UI', '10', 'bold'), bd=6)
        frame.grid(row=0, column=3, rowspan=4, padx=5, pady=5, sticky='n')
        frame.bind('<Enter>', lambda event: frame.focus_set()) # force update
        self.tbl_inner_frame = tk.LabelFrame(frame)
        self.tbl_inner_frame.grid()
        button_width, button_height = 20, 2
        bold_width_adjust = -3
        spinbox_width = 20
        # snap:
        snap_button = tk.Button(
            self.tbl_inner_frame,
            text="Snap",
            command=self._tbl_snap_and_display,
            font=('Segoe UI', '10', 'bold'),
            width=button_width + bold_width_adjust,
            height=button_height)
        snap_button.grid(row=0, column=0, padx=10, pady=10)
        snap_button_tip = Hovertip(snap_button, "tip...")
        # live mode:
        def _live_mode():
            if self.tbl_running_live_mode.get():
                self._set_running_mode('tbl_live_mode')
            else:
                self._set_running_mode('None')
            def _run_live_mode():
                if self.tbl_running_live_mode.get():
                    if not self.last_acquire_task.is_alive():
                        self._tbl_snap_and_display()
                    self.root.after(int(1e3/30), _run_live_mode) # 30 fps
                return None
            _run_live_mode()
            return None
        self.tbl_running_live_mode = tk.BooleanVar()
        live_mode_button = tk.Checkbutton(
            self.tbl_inner_frame,
            text='Live mode (On/Off)',
            variable=self.tbl_running_live_mode,
            command=_live_mode,
            indicatoron=0,
            font=('Segoe UI', '10', 'italic'),
            width=button_width,
            height=button_height)
        live_mode_button.grid(row=1, column=0, padx=10, pady=10)
        live_mode_button_tip = Hovertip(live_mode_button, "tip...")
        # save image:
        def _save_image():
            if self.tbl_images_per_buffer.value.get() != 1:
                self.tbl_images_per_buffer.update_and_validate(1)
            folder_name = self._tbl_get_folder_name() + '_snap'
            self.last_acquire_task.get_result() # don't accumulate acquires
            self.scope.tbl_acquire(
                filename='snap.tif',
                folder_name=folder_name,
                description=self.tbl_description_textbox.text)
            return None
        save_image_button = tk.Button(
            self.tbl_inner_frame,
            text="Save image",
            command=_save_image,
            font=('Segoe UI', '10', 'bold'),
            fg='blue',
            width=button_width + bold_width_adjust,
            height=button_height)
        save_image_button.grid(row=3, column=0, padx=10, pady=10)
        save_image_tip = Hovertip(save_image_button, "tip...")
        # run acquire:
        def _acquire():
            print('\nAcquire -> started')
            self._set_running_mode('tbl_acquire')
            self.folder_name = self._tbl_get_folder_name() + '_acquire'
            self.delay_saved = False
            self.acquire_count = 0
            def _run_acquire():
                if not self.tbl_running_acquire.get(): # check for cancel
                    return None
                # don't launch all tasks: either wait 1 buffer time or delay:
                wait_ms = int(round(1e3 * self.scope.tbl_buffer_time_s))
                self.scope.tbl_acquire(
                    filename='%06i.tif'%self.acquire_count,
                    folder_name=self.folder_name,
                    description=self.tbl_description_textbox.text)
                self.acquire_count += 1
                if self.tbl_delay_s.value.get() > self.scope.tbl_buffer_time_s:
                    wait_ms = int(round(1e3 * self.tbl_delay_s.value.get()))                    
                # record gui delay:
                if (not self.delay_saved and os.path.exists(
                    self.folder_name)):
                    with open(self.folder_name + '\\'  "gui_delay_s.txt",
                              "w") as file:
                        file.write(self.folder_name + '\n')
                        file.write(
                            'gui_delay_s: %i'%self.tbl_delay_s.value.get() +
                            '\n')
                        self.delay_saved = True
                # check acquire count before re-run:
                if self.acquire_count < self.tbl_acquire_number.value.get():
                    self.root.after(wait_ms, _run_acquire)
                else:
                    self.scope.finish_all_tasks()
                    self._set_running_mode('None')
                    print('Acquire -> finished\n')
                return None
            _run_acquire()
            return None
        self.tbl_running_acquire = tk.BooleanVar()
        acquire_button = tk.Checkbutton(
            self.tbl_inner_frame,
            text="Run acquire",
            variable=self.tbl_running_acquire,
            command=_acquire,
            indicatoron=0,
            font=('Segoe UI', '10', 'bold'),
            fg='red',
            width=button_width + bold_width_adjust,
            height=button_height)
        acquire_button.grid(row=4, column=0, padx=10, pady=10)
        acquire_button_tip = Hovertip(acquire_button, "tip...")
        return None

    def init_exit(self):
        frame = tk.LabelFrame(
            self.root, text='EXIT', font=('Segoe UI', '10', 'bold'), bd=6)
        frame.grid(row=5, column=0, columnspan=2, padx=5, pady=5)
        def _exit():
            if self.init_microscope: self.scope.close()
            self.root.quit()
            return None
        exit_button = tk.Button(
            frame,
            text="EXIT GUI",
            command=_exit,
            height=2,
            width=25)
        exit_button.grid(row=0, column=0, padx=10, pady=10, sticky='n')
        exit_button_tip = Hovertip(exit_button, "tip...")
        return None

    def init_running_mode(self):
        # define mode variable and dictionary:
        self.running_mode = tk.StringVar()
        self.mode_to_variable = {
            'epi_live_mode':    self.epi_running_live_mode,
            'epi_acquire':      self.epi_running_acquire,
            'tbl_live_mode':    self.tbl_running_live_mode,
            'tbl_acquire':      self.tbl_running_acquire,
            }
        # cancel running mode popup:
        self.cancel_running_mode_popup = tk.Toplevel()
        self.cancel_running_mode_popup.title('Cancel current process')
        x, y = self.root.winfo_x(), self.root.winfo_y() # center popup
        self.cancel_running_mode_popup.geometry("+%d+%d" % (x + 1200, y + 600))
        self.cancel_running_mode_popup.withdraw()
        # cancel button:
        def _cancel():
            print('\n *** Canceled -> ' + self.running_mode.get() + ' *** \n')
            self._set_running_mode('None')
            return None
        self.cancel_running_mode_button = tk.Button(
            self.cancel_running_mode_popup,
            font=('Segoe UI', '10', 'bold'),
            bg='red',
            command=_cancel,
            width=25,
            height=2)
        self.cancel_running_mode_button.grid(row=8, column=0, padx=10, pady=10)
        cancel_running_mode_tip = Hovertip(
            self.cancel_running_mode_button,
            "Cancel the current process.\n" +
            "NOTE: this is not immediate since some processes must finish\n" +
            "once launched.")
        return None

    def _set_running_mode(self, mode):
        if mode != 'None':
            # turn everything off except current mode:
            for v in self.mode_to_variable.values():
                if v != self.mode_to_variable[mode]:
                    v.set(0)
        if mode in ('epi_acquire', 'tbl_acquire'):
            # update cancel text:
            self.running_mode.set(mode) # string for '_cancel' print
            self.cancel_running_mode_button.config(text=('Cancel: ' + mode))
            # display cancel popup and grab set:
            self.cancel_running_mode_popup.deiconify()
            self.cancel_running_mode_popup.grab_set()
        if mode == 'None':
            # turn everything off:
            for v in self.mode_to_variable.values():
                v.set(0)
            # hide cancel popup and release set:
            self.cancel_running_mode_popup.withdraw()
            self.cancel_running_mode_popup.grab_release()
        return None

if __name__ == '__main__':
    gui_microscope = GuiMicroscope(init_microscope=True)
