import tkinter as tk
from tkinter import ttk
import json
import threading
from pynput import mouse, keyboard
import time
from pathlib import Path
import sys

class ProfileManager:
    def __init__(self, path="profiles.json"):
        self.path = Path(path)
        self.profiles = {}
        self.load()
    
    def load(self):
        if self.path.exists():
            with self.path.open("r") as f:
                self.profiles = json.load(f)
    
    def save(self):
        with self.path.open("w") as f:
            json.dump(self.profiles, f)
    
    def get_profile(self, name):
        return self.profiles.get(name, {
            'repeat_count': 1,
            'infinite': False,
            'gap': 0,
            'recordings': {}
        })
    
    def update_profile(self, name, data):
        self.profiles[name] = data
        self.save()
    
    def delete_profile(self, name):
        if name in self.profiles:
            del self.profiles[name]
            self.save()

class MouseRecorder:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Mouse Recorder")
        self.root.geometry("800x500")
        
        # Set up app icon
        try:
            # Get the directory where the script is located
            script_dir = Path(__file__).parent
            icon_path = script_dir / "assets" / "icon.ico"
            
            # Create assets directory if it doesn't exist
            assets_dir = script_dir / "assets"
            assets_dir.mkdir(exist_ok=True)
            
            if icon_path.exists():
                self.root.iconbitmap(icon_path)
            else:
                print(f"Icon not found at: {icon_path}")
                print("Please place 'icon.ico' in the assets folder")
        except Exception as e:
            print(f"Error loading icon: {e}")
        
        # Variables
        self.recording = False
        self.playing = False
        self.current_recording = []
        self.recordings = {}
        self.recording_thread = None
        self.mouse_controller = mouse.Controller()
        
        # Add profile variables
        self.profiles = {}
        self.current_profile = None
        
        self.profile_manager = ProfileManager()
        
        self.setup_gui()
        self.load_profiles()
        self.setup_hotkeys()

    def setup_gui(self):
        # Set up window attributes
        self.root.attributes('-topmost', False)
        self.root.geometry("800x500")  # Slightly larger default size
        
        # Main container with padding
        self.main_container = ttk.Frame(self.root, padding="10")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Profile section at top
        profile_frame = ttk.LabelFrame(self.main_container, text="Profile", padding="10")
        profile_frame.pack(fill=tk.X, pady=(0, 10))
        
        profile_controls = ttk.Frame(profile_frame)
        profile_controls.pack(fill=tk.X)
        
        self.profile_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(
            profile_controls,
            textvariable=self.profile_var,
            state="readonly",
            width=30
        )
        self.profile_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.profile_combo.bind('<<ComboboxSelected>>', self.load_profile)
        
        # Profile buttons in a separate frame
        profile_buttons = ttk.Frame(profile_controls)
        profile_buttons.pack(side=tk.LEFT)
        
        # Profile buttons with better emojis
        for btn_text, cmd in [
            ("➕ New", self.new_profile),
            ("Rename", self.rename_profile),
            ("Save", self.save_profile),
            ("Delete", self.delete_profile)
        ]:
            ttk.Button(
                profile_buttons,
                text=btn_text,
                command=cmd,
                width=10
            ).pack(side=tk.LEFT, padx=2)
        
        # Main content area
        content_frame = ttk.Frame(self.main_container)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Recordings list
        left_panel = ttk.Frame(content_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        list_frame = ttk.LabelFrame(left_panel, text="Saved Recordings", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Recordings list with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.recordings_list = tk.Listbox(
            list_container,
            borderwidth=1,
            highlightthickness=0,
            selectmode=tk.SINGLE
        )
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.recordings_list.yview)
        self.recordings_list.configure(yscrollcommand=scrollbar.set)
        
        self.recordings_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Recording buttons in a frame
        recording_buttons = ttk.Frame(list_frame)
        recording_buttons.pack(fill=tk.X)
        
        # Recording buttons with better emojis
        for btn_text, cmd in [
            ("Rename", self.rename_recording),
            ("Delete", self.delete_recording)
        ]:
            ttk.Button(
                recording_buttons,
                text=btn_text,
                command=cmd,
                width=10
            ).pack(side=tk.RIGHT, padx=2)
        
        # Right panel - Controls
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH)
        
        # Main controls
        controls_frame = ttk.LabelFrame(right_panel, text="Controls", padding="10")
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Main action buttons with better emojis
        for btn_text, cmd, style in [
            ("⚫ Start Recording (F6)", self.toggle_recording, "Record.TButton"),
            ("▶️ Play Recording (F7)", self.play_recording, "Play.TButton"),
            ("⏹️ Stop Playback (F8/ESC)", self.stop_playback, "Stop.TButton")
        ]:
            btn = ttk.Button(
                controls_frame,
                text=btn_text,
                command=cmd,
                style=style
            )
            btn.pack(fill=tk.X, pady=(0, 5))
            if "Stop" in btn_text:
                self.stop_button = btn
                btn.configure(state="disabled")
        
        # Settings frame
        settings_frame = ttk.LabelFrame(right_panel, text="Playback Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Settings grid for better alignment
        settings_grid = ttk.Frame(settings_frame)
        settings_grid.pack(fill=tk.X)
        
        # Repeat settings
        ttk.Label(settings_grid, text="Repeats:").grid(row=0, column=0, sticky="w", padx=5)
        self.repeat_count = ttk.Spinbox(
            settings_grid,
            from_=1,
            to=999,
            width=5
        )
        self.repeat_count.grid(row=0, column=1, sticky="w", padx=5)
        
        self.infinite_loop = tk.BooleanVar()
        ttk.Checkbutton(
            settings_grid,
            text="Infinite",
            variable=self.infinite_loop
        ).grid(row=0, column=2, sticky="w", padx=5)
        
        # Gap settings
        ttk.Label(settings_grid, text="Gap (seconds):").grid(row=1, column=0, sticky="w", padx=5)
        self.gap_duration = ttk.Spinbox(
            settings_grid,
            from_=0,
            to=60,
            width=5,
            increment=0.5
        )
        self.gap_duration.grid(row=1, column=1, sticky="w", padx=5)
        
        # Always on top setting
        self.always_on_top = tk.BooleanVar()
        ttk.Checkbutton(
            settings_grid,
            text="Always on Top",
            variable=self.always_on_top,
            command=self.toggle_always_on_top
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 0))
        
        # Status bar at bottom
        status_frame = ttk.Frame(self.main_container)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_label = ttk.Label(
            status_frame,
            text="Ready",
            foreground="green"
        )
        self.status_label.pack(side=tk.LEFT)

    def setup_hotkeys(self):
        # Register hotkeys with and without Ctrl
        self.listener = keyboard.GlobalHotKeys({
            '<f6>': self.toggle_recording,
            '<ctrl>+<f6>': self.toggle_recording,
            '<f7>': self.play_recording,
            '<ctrl>+<f7>': self.play_recording,
            '<f8>': self.stop_playback,
            '<ctrl>+<f8>': self.stop_playback,
            '<esc>': self.stop_playback
        })
        self.listener.start()

    def toggle_recording(self):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        if self.playing:
            return
            
        self.recording = True
        self.current_recording = []
        self.stop_button.configure(state="normal")
        self.status_label.configure(text="Recording...", foreground="red")
        
        def record():
            start_time = time.time()
            last_pos = None
            min_distance = 5  # Minimum pixels to move before recording
            last_update_time = 0
            update_interval = 0.05  # 50ms minimum between position updates
            
            def on_move(x, y):
                nonlocal last_pos, last_update_time
                
                if not self.recording:
                    return
                    
                current_time = time.time()
                
                # Skip if update interval hasn't elapsed
                if current_time - last_update_time < update_interval:
                    return
                    
                # Only record if mouse moved significantly
                if last_pos:
                    dx = x - last_pos[0]
                    dy = y - last_pos[1]
                    if (dx * dx + dy * dy) < min_distance * min_distance:
                        return
                
                last_pos = (x, y)
                last_update_time = current_time
                
                self.current_recording.append({
                    't': 'm',  # Shortened type
                    'x': round(x),  # Round coordinates
                    'y': round(y),
                    'e': round(current_time - start_time, 3)  # Shortened time key, rounded
                })
            
            def on_click(x, y, button, pressed):
                if self.recording:
                    self.current_recording.append({
                        't': 'c',  # Shortened type
                        'x': round(x),
                        'y': round(y),
                        'b': str(button).split('.')[-1],  # Store only button name
                        'p': pressed,
                        'e': round(time.time() - start_time, 3)
                    })
            
            with mouse.Listener(on_move=on_move, on_click=on_click) as listener:
                listener.join()
        
        self.recording_thread = threading.Thread(target=record, daemon=True)
        self.recording_thread.start()

    def stop_recording(self):
        self.recording = False
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="✅ Ready", foreground="green")
        
        if self.current_recording:
            name = f"📌 Recording {len(self.recordings) + 1}"
            self.recordings[name] = self.current_recording
            self.update_recordings_list()
            # Select the new recording
            last_index = self.recordings_list.size() - 1
            if last_index >= 0:
                self.recordings_list.selection_clear(0, tk.END)
                self.recordings_list.selection_set(last_index)
                self.recordings_list.see(last_index)
            self.save_recordings()

    def play_recording(self):
        if self.recording or self.playing:
            return
        
        selection = self.recordings_list.curselection()
        if not selection:
            # If nothing selected and there are recordings, select the last one
            if self.recordings_list.size() > 0:
                last_index = self.recordings_list.size() - 1
                self.recordings_list.selection_clear(0, tk.END)
                self.recordings_list.selection_set(last_index)
                self.recordings_list.see(last_index)
                selection = (last_index,)
            else:
                return
        
        name = self.recordings_list.get(selection[0])
        actions = self.recordings[name]
        
        try:
            repeat_count = int(self.repeat_count.get())
            gap_seconds = float(self.gap_duration.get())
        except ValueError:
            repeat_count = 1
            gap_seconds = 0
        
        self.playing = True
        self.stop_button.configure(state="normal")
        
        def play():
            repeat_num = 1
            status_update_time = 0
            status_update_interval = 0.02  # More frequent updates (20ms)
            
            while self.playing:
                # Calculate total time for this iteration
                total_time = actions[-1]['e'] if actions else 0
                
                start_time = time.time()
                mouse_pos = None
                
                for action in actions:
                    if not self.playing:
                        break
                    
                    # Calculate and show remaining time
                    current_time = time.time()
                    elapsed = current_time - start_time
                    remaining = total_time - elapsed
                    
                    if current_time - status_update_time >= status_update_interval:
                        status = f"▶️ Playing... {remaining:.1f}s left"
                        if not self.infinite_loop.get():
                            status += f" ({repeat_num}/{repeat_count})"
                        else:
                            status += f" (∞ - {repeat_num})"
                        self.status_label.configure(text=status, foreground="blue")
                        status_update_time = current_time
                    
                    # Check if we should wait for timing
                    wait_time = action['e'] - (current_time - start_time)
                    if wait_time > 0:
                        # Break wait into small chunks for quick stopping
                        while wait_time > 0 and self.playing:
                            sleep_time = min(0.01, wait_time)  # Max 10ms chunks
                            time.sleep(sleep_time)
                            wait_time -= sleep_time
                            
                            # Update status during wait
                            current_time = time.time()
                            if current_time - status_update_time >= status_update_interval:
                                elapsed = current_time - start_time
                                remaining = total_time - elapsed
                                status = f"▶️ Playing... {remaining:.1f}s left"
                                if not self.infinite_loop.get():
                                    status += f" ({repeat_num}/{repeat_count})"
                                else:
                                    status += f" (∞ - {repeat_num})"
                                self.status_label.configure(text=status, foreground="blue")
                                status_update_time = current_time
                    
                    if not self.playing:
                        break
                    
                    # Perform the action
                    if action['t'] == 'm':
                        new_x = action['x']
                        new_y = action['y']
                        if not mouse_pos or abs(mouse_pos[0] - new_x) > 5 or abs(mouse_pos[1] - new_y) > 5:
                            self.mouse_controller.position = (new_x, new_y)
                            mouse_pos = (new_x, new_y)
                    elif action['t'] == 'c':
                        self.mouse_controller.position = (action['x'], action['y'])
                        mouse_pos = (action['x'], action['y'])
                        if action['p']:
                            self.mouse_controller.press(getattr(mouse.Button, action['b']))
                        else:
                            self.mouse_controller.release(getattr(mouse.Button, action['b']))
                
                if not self.playing:
                    break
                
                if not self.infinite_loop.get():
                    if repeat_num >= repeat_count:
                        break
                    repeat_num += 1
                else:
                    repeat_num += 1
                
                if gap_seconds > 0 and self.playing:
                    gap_start = time.time()
                    while self.playing and (time.time() - gap_start) < gap_seconds:
                        current_time = time.time()
                        if current_time - status_update_time >= status_update_interval:
                            remaining_gap = gap_seconds - (current_time - gap_start)
                            status = f"⏳ Gap: {remaining_gap:.1f}s left"
                            if not self.infinite_loop.get():
                                status += f" ({repeat_num}/{repeat_count})"
                            else:
                                status += f" (∞ - {repeat_num})"
                            self.status_label.configure(text=status, foreground="orange")
                            status_update_time = current_time
                        time.sleep(0.01)  # Small sleep chunks for quick stopping
        
            self.playing = False
            self.stop_button.configure(state="disabled")
            self.status_label.configure(text="✅ Ready", foreground="green")
        
        threading.Thread(target=play, daemon=True).start()

    def stop_playback(self):
        if self.playing:
            self.playing = False
            self.stop_button.configure(state="disabled")
            self.status_label.configure(text="⏹️ Stopped", foreground="red")
            # Change back to ready after a short delay
        self.playing = False

    def delete_recording(self):
        selection = self.recordings_list.curselection()
        if not selection:
            return
            
        name = self.recordings_list.get(selection[0])
        del self.recordings[name]
        self.update_recordings_list()
        self.save_recordings()

    def update_recordings_list(self):
        self.recordings_list.delete(0, tk.END)
        for name in self.recordings:
            self.recordings_list.insert(tk.END, name)

    def save_recordings(self):
        self.save_profile()

    def load_recordings(self):
        pass  # Now handled by profile loading

    def new_profile(self):
        name = f"⭐ Profile {len(self.profiles) + 1}"
        self.profiles[name] = {
            'repeat_count': 1,
            'infinite': False,
            'gap': 0,
            'recordings': {},
            'always_on_top': False  # Add default value
        }
        self.update_profile_list()
        self.profile_combo.set(name)
        self.load_profile()
        self.save_profiles()

    def save_profile(self):
        if not self.current_profile:
            return
        
        profile_data = {
            'repeat_count': int(self.repeat_count.get()),
            'infinite': self.infinite_loop.get(),
            'gap': float(self.gap_duration.get()),
            'recordings': self.recordings,
            'always_on_top': self.always_on_top.get()  # Save always on top state
        }
        self.profile_manager.update_profile(self.current_profile, profile_data)

    def delete_profile(self):
        if not self.current_profile:
            return
        
        del self.profiles[self.current_profile]
        self.update_profile_list()
        
        if self.profiles:
            self.profile_combo.set(list(self.profiles.keys())[0])
            self.load_profile()
        else:
            self.new_profile()
        
        self.save_profiles()

    def load_profile(self, event=None):
        name = self.profile_var.get()
        if not name or name not in self.profiles:
            return
        
        self.current_profile = name
        profile = self.profiles[name]
        
        self.repeat_count.set(profile['repeat_count'])
        self.infinite_loop.set(profile['infinite'])
        self.gap_duration.set(profile['gap'])
        self.recordings = profile['recordings'].copy()
        
        # Load always on top state
        always_on_top = profile.get('always_on_top', False)  # Default to False if not saved
        self.always_on_top.set(always_on_top)
        self.root.attributes('-topmost', always_on_top)
        
        self.update_recordings_list()

    def update_profile_list(self):
        self.profile_combo['values'] = list(self.profiles.keys())

    def save_profiles(self):
        self.profile_manager.save()

    def load_profiles(self):
        self.profiles = self.profile_manager.profiles
        if not self.profiles:
            # Create default profiles including Skype
            self.create_default_profiles()
        else:
            self.current_profile = list(self.profiles.keys())[0]
            self.update_profile_list()
            self.profile_combo.set(self.current_profile)
            self.load_profile()

    def create_default_profiles(self):
        # Create Skype keep-active profile
        current_pos = self.mouse_controller.position  # Get current position
        skype_profile = {
            'repeat_count': 1,
            'infinite': True,
            'gap': 240,
            'recordings': {
                '🔄 Keep Active': [
                    # Small movement relative to current position
                    {'t': 'm', 'x': current_pos[0], 'y': current_pos[1], 'e': 0.0},
                    {'t': 'm', 'x': current_pos[0] + 5, 'y': current_pos[1], 'e': 0.2},
                    {'t': 'm', 'x': current_pos[0] + 5, 'y': current_pos[1] + 5, 'e': 0.4},
                    {'t': 'm', 'x': current_pos[0], 'y': current_pos[1] + 5, 'e': 0.6},
                    {'t': 'm', 'x': current_pos[0], 'y': current_pos[1], 'e': 0.8}
                ]
            },
            'always_on_top': False
        }
        
        # Add profiles with better emojis
        self.profiles["💻 Skype Keep Active"] = skype_profile
        self.profiles["⭐ Default Profile"] = {
            'repeat_count': 1,
            'infinite': False,
            'gap': 0,
            'recordings': {},
            'always_on_top': False
        }
        
        # Set current profile to Skype
        self.current_profile = "💻 Skype Keep Active"
        self.update_profile_list()
        self.profile_combo.set(self.current_profile)
        self.load_profile()
        self.save_profiles()

    def toggle_always_on_top(self):
        self.root.attributes('-topmost', self.always_on_top.get())
        self.save_profile()  # Save the setting

    def rename_recording(self):
        selection = self.recordings_list.curselection()
        if not selection:
            return
        
        old_name = self.recordings_list.get(selection[0])
        dialog = RenameDialog(self.root, "Rename Recording", old_name)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result and dialog.result != old_name:
            # Update recordings dict
            self.recordings[dialog.result] = self.recordings.pop(old_name)
            
            # Update list and maintain selection
            self.update_recordings_list()
            new_index = list(self.recordings.keys()).index(dialog.result)
            self.recordings_list.selection_clear(0, tk.END)
            self.recordings_list.selection_set(new_index)
            self.recordings_list.see(new_index)
            
            self.save_profile()

    def rename_profile(self):
        if not self.current_profile:
            return
        
        dialog = RenameDialog(self.root, "Rename Profile", self.current_profile)
        self.root.wait_window(dialog.dialog)
        
        if dialog.result and dialog.result != self.current_profile:
            # Update profiles dict
            self.profiles[dialog.result] = self.profiles.pop(self.current_profile)
            self.current_profile = dialog.result
            
            # Update UI
            self.update_profile_list()
            self.profile_combo.set(dialog.result)
            
            self.save_profiles()

    def run(self):
        self.root.mainloop()

class RenameDialog:
    def __init__(self, parent, title, current_name):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("300x100")
        self.dialog.transient(parent)  # Make dialog modal
        self.dialog.grab_set()
        
        self.result = None
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (
            parent.winfo_rootx() + parent.winfo_width()/2 - 150,
            parent.winfo_rooty() + parent.winfo_height()/2 - 50
        ))
        
        # Add widgets
        frame = ttk.Frame(self.dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="New name:").pack(pady=(0, 5))
        
        self.name_var = tk.StringVar(value=current_name)
        self.entry = ttk.Entry(frame, textvariable=self.name_var)
        self.entry.pack(fill=tk.X, pady=(0, 10))
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="OK", command=self.ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT)
        
        self.entry.select_range(0, tk.END)
        self.entry.focus_set()
        self.dialog.bind('<Return>', lambda e: self.ok())
        self.dialog.bind('<Escape>', lambda e: self.cancel())
    
    def ok(self):
        self.result = self.name_var.get()
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()

if __name__ == "__main__":
    app = MouseRecorder()
    app.run()
