import os
import hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import time
from queue import Queue
import datetime

class FileHashCheckerApp: # Clase principal de la aplicación
    def __init__(self, root):
        # Inicialización de la aplicación principal
        self.root = root
        self.root.title("File Hash Checker")
        self.setup_ui()
        self.setup_styles()

        # Variables de estado
        self.selected_folder = ""
        self.processing = False
        self.stop_requested = False
        self.file_queue = Queue()
        self.duplicates = {}
        self.current_group = []
        self.image_references = []
        self.selected_files = set()
        self.checkboxes = []

        # Iniciar el procesamiento periódico de la cola
        self.root.after(100, self.process_queue)

    def setup_styles(self):
        """Configura los estilos visuales para la interfaz oscura"""
        style = ttk.Style()
        style.theme_use('clam')  # Tema base
        # Configurar colores para diferentes componentes background para el fondo y foreground para texto
        style.configure('.', background='#333333', foreground='white')
        style.configure('TButton', background='#444444', foreground='white')
        style.configure('TFrame', background='#333333')
        style.configure('TLabel', background='#333333', foreground='white')
        style.configure('TProgressbar', troughcolor='#444444', background='#0066cc')
        style.configure('TEntry', fieldbackground='#444444', foreground='white')
        style.configure('TCheckbutton', background='#333333', foreground='white')
        style.map('TButton', background=[('active', '#555555'), ('disabled', '#333333')])

    def setup_ui(self):
        """Construye todos los componentes de la interfaz gráfica"""
        # Marco superior con botones principales
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        # Botones de control
        self.btn_examine = ttk.Button(top_frame, text="Examinar carpeta", command=self.select_folder)
        self.btn_examine.pack(side=tk.LEFT, padx=5)

        self.btn_start = ttk.Button(top_frame, text="Iniciar", command=self.start_processing, state=tk.DISABLED)
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(top_frame, text="Detener", command=self.stop_processing, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        self.lbl_folder = ttk.Label(top_frame, text="Carpeta no seleccionada")
        self.lbl_folder.pack(side=tk.LEFT, padx=10)

        # Área principal con scroll para los duplicados
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Configuración del sistema de scroll
        self.canvas = tk.Canvas(main_frame, bg='#333333', highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        # Vinculación del área scrollable
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Área de registro (log)
        log_frame = ttk.Frame(self.root, padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=10, bg='#444444', fg='white', insertbackground='white')
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Barra de progreso y botón de exportar
        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill=tk.X)

        self.progress = ttk.Progressbar(bottom_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress.pack(fill=tk.X, expand=True, side=tk.LEFT)

        self.btn_export = ttk.Button(bottom_frame, text="Exportar Log", command=self.export_log)
        self.btn_export.pack(side=tk.RIGHT, padx=5)

        # Botones de acción para archivos seleccionados
        action_frame = ttk.Frame(self.root, padding=10)
        action_frame.pack(fill=tk.X)

        self.btn_move = ttk.Button(action_frame, text="Mover seleccionados", command=self.move_selected, state=tk.DISABLED)
        self.btn_move.pack(side=tk.LEFT, padx=5)

        self.btn_delete = ttk.Button(action_frame, text="Borrar seleccionados", command=self.delete_selected, state=tk.DISABLED)
        self.btn_delete.pack(side=tk.LEFT, padx=5)

    def select_folder(self):
        """Manejador para seleccionar carpeta mediante diálogo"""
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder = folder
            self.lbl_folder.config(text=folder)
            self.btn_start.config(state=tk.NORMAL)
            self.log("Carpeta seleccionada: " + folder)

    def log(self, message):
        """Agrega un mensaje al registro con marca de tiempo"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

    def export_log(self):
        """Exporta el contenido del log a un archivo de texto"""
        log_content = self.log_text.get("1.0", tk.END)
        file_path = filedialog.asksaveasfilename(defaultextension=".txt")
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(log_content)
                self.log("Log exportado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo exportar el log: {str(e)}")

    def start_processing(self):
        """Inicia el proceso de análisis en un hilo separado"""
        if self.selected_folder:
            self.processing = True
            self.stop_requested = False
            # Actualizar estados de los botones
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_examine.config(state=tk.DISABLED)
            self.progress['value'] = 0
            # Iniciar hilo de procesamiento
            threading.Thread(target=self.process_files, daemon=True).start()

    def stop_processing(self):
        """Detiene el procesamiento en curso"""
        self.stop_requested = True
        self.log("Proceso detenido por el usuario")
        self.cleanup_processing()

    def cleanup_processing(self):
        """Restaura el estado inicial de la interfaz después del procesamiento"""
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_examine.config(state=tk.NORMAL)
        self.processing = False

    def process_files(self):
        """Procesa todos los archivos en la carpeta seleccionada para encontrar duplicados"""
        self.log("Iniciando procesamiento de archivos...")
        all_files = []
        # Recorrer recursivamente la carpeta
        for root, dirs, files in os.walk(self.selected_folder):
            if self.stop_requested:
                break
            for file in files:
                all_files.append(os.path.join(root, file))

        total_files = len(all_files)
        self.progress['maximum'] = total_files
        hashes = {}

        # Calcular hash para cada archivo
        for i, file_path in enumerate(all_files):
            if self.stop_requested:
                break

            file_hash = self.calculate_hash(file_path)
            if file_hash:
                if file_hash in hashes:
                    hashes[file_hash].append(file_path)
                else:
                    hashes[file_hash] = [file_path]

            # Actualizar barra de progreso
            self.progress['value'] = i + 1
            self.root.update_idletasks()

        # Filtrar solo los hashes con duplicados
        self.duplicates = {k: v for k, v in hashes.items() if len(v) > 1}
        self.file_queue.put(("duplicates", self.duplicates))
        self.cleanup_processing()
        self.log(f"Proceso completado. Grupos de duplicados encontrados: {len(self.duplicates)}")

    def calculate_hash(self, file_path, chunk_size=8192):
        """Calcula el hash SHA-256 de un archivo"""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    if self.stop_requested:
                        return None
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            self.log(f"Error al procesar {file_path}: {str(e)}")
            return None

    def process_queue(self):
        """Procesa los mensajes en la cola de forma asíncrona"""
        try:
            while True:
                task = self.file_queue.get_nowait()
                if task[0] == "duplicates":
                    self.show_all_duplicates(task[1])
        except:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def show_all_duplicates(self, duplicates):
        """Muestra todos los grupos de duplicados en la interfaz"""
        self.clear_scrollable_area()
        self.selected_files = set()
        self.checkboxes = []

        # Este if verifica si hay duplicados en la carpeta seleccionada
        if not duplicates:
            self.log("No se encontraron archivos duplicados")
            return

        # Crear elementos de interfaz para cada grupo de duplicados
        for group_id, (hash_value, file_group) in enumerate(duplicates.items()):
            # Marco para cada grupo
            group_frame = ttk.Frame(self.scrollable_frame, borderwidth=2, relief="groove")
            group_frame.pack(fill=tk.X, pady=5, padx=5)

            # Encabezado del grupo
            header = ttk.Frame(group_frame)
            header.pack(fill=tk.X, padx=5, pady=2)
            ttk.Label(header, text=f"Grupo {group_id + 1} - {len(file_group)} archivos",
                     font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

            # Contenedor para los archivos del grupo
            files_frame = ttk.Frame(group_frame)
            files_frame.pack(fill=tk.X, padx=10, pady=5)

            # Elementos individuales para cada archivo
            for idx, file_path in enumerate(file_group):
                file_frame = ttk.Frame(files_frame)
                file_frame.pack(side=tk.LEFT, padx=5, pady=5)

                # Checkbox de selección
                var = tk.BooleanVar()
                self.checkboxes.append((var, file_path))
                cb = ttk.Checkbutton(
                    file_frame,
                    variable=var,
                    command=lambda v=var, fp=file_path: self.toggle_selection(v, fp)
                )
                cb.pack() # Colocar checkbox en la ventana

                # Vista previa del archivo
                preview_frame = ttk.Frame(file_frame)
                preview_frame.pack(pady=5)
                self.display_file(file_path, preview_frame)

        # Habilitar botones de acción
        self.btn_move.config(state=tk.NORMAL)
        self.btn_delete.config(state=tk.NORMAL)

    def toggle_selection(self, var, file_path):
        """Manejador para cambios en los checkboxes de selección"""
        if var.get():
            self.selected_files.add(file_path)
        else:
            self.selected_files.discard(file_path)

    def clear_scrollable_area(self):
        """Limpia el área de visualización de duplicados"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.image_references = []

    def display_file(self, file_path, parent):
        """Muestra la vista previa de un archivo en la interfaz"""
        try: # Intentar mostrar la vista previa del archivo
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                img = Image.open(file_path)
                img.thumbnail((70, 70))
                photo = ImageTk.PhotoImage(img)
                self.image_references.append(photo)
                label = ttk.Label(parent, image=photo)
                label.image = photo
                label.pack(pady=5)
            else:  # Icono para archivos no imágenes
                icon_label = ttk.Label(parent, text="📄", font=('Arial', 32))
                icon_label.pack(pady=5)

            # Información del archivo
            file_label = ttk.Label(parent, text=os.path.basename(file_path), wraplength=300)
            file_label.pack()
            path_label = ttk.Label(parent, text=file_path, wraplength=200, font=('Arial', 8))
            path_label.pack()
        except Exception as e:
            self.log(f"Error al mostrar {file_path}: {str(e)}")

    def move_selected(self):
        """Mueve los archivos seleccionados a otra carpeta"""
        if not self.selected_files:
            messagebox.showwarning("Advertencia", "No hay archivos seleccionados")
            return

        dest = filedialog.askdirectory()
        if dest:
            for file_path in list(self.selected_files):
                try:
                    os.rename(file_path, os.path.join(dest, os.path.basename(file_path)))
                    self.log(f"Archivo movido: {file_path}")
                    self.remove_file_from_groups(file_path)
                except Exception as e:
                    self.log(f"Error moviendo archivo: {str(e)}")
            self.refresh_duplicates_display()

    def delete_selected(self):
        """Elimina los archivos seleccionados permanentemente"""
        if not self.selected_files:
            messagebox.showwarning("Advertencia", "No hay archivos seleccionados")
            return

        if messagebox.askyesno("Confirmar", "¿Está seguro de eliminar los archivos seleccionados?"):
            for file_path in list(self.selected_files):
                try:
                    os.remove(file_path)
                    self.log(f"Archivo eliminado: {file_path}")
                    self.remove_file_from_groups(file_path)
                except Exception as e:
                    self.log(f"Error eliminando archivo: {str(e)}")
            self.refresh_duplicates_display()

    def remove_file_from_groups(self, file_path):
        """Elimina un archivo de los grupos de duplicados"""
        for hash_value in list(self.duplicates.keys()):
            if file_path in self.duplicates[hash_value]:
                self.duplicates[hash_value].remove(file_path)
                # Eliminar grupo si queda con menos de 2 archivos
                if len(self.duplicates[hash_value]) < 2:
                    del self.duplicates[hash_value]

    def refresh_duplicates_display(self):
        """Actualiza la visualización de duplicados después de cambios"""
        self.show_all_duplicates(self.duplicates)
        # Deshabilitar botones si no hay duplicados
        if not self.duplicates:
            self.btn_move.config(state=tk.DISABLED)
            self.btn_delete.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1000x700")
    app = FileHashCheckerApp(root)
    root.mainloop()