import os

# Define the folders to scan inside the `app/` package
folders = ["api", "models", "schemas", "services", "templates", "tests", "static"]

# Compute the app base path relative to this script (scripts/ is at repo root)
this_dir = os.path.dirname(os.path.abspath(__file__))
base_path = os.path.abspath(os.path.join(this_dir, "..", "app"))

# Output goes into a 'references' subfolder next to this script
output_root = os.path.join(this_dir, "references")
os.makedirs(output_root, exist_ok=True)

for folder in folders:
    folder_path = os.path.join(base_path, folder)
    print(f"Procesando carpeta: {folder_path}")
    txt_filename = f"{folder}.txt"
    txt_path = os.path.join(output_root, txt_filename)
    with open(txt_path, "w", encoding="utf-8") as txt_file:
        if not os.path.isdir(folder_path):
            txt_file.write(f"Carpeta '{folder}' no encontrada en {base_path}.\n")
            continue
        for root, _, files in os.walk(folder_path):
            # Omitir carpetas __pycache__
            if "__pycache__" in root.split(os.sep):
                continue
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    relpath = os.path.relpath(file_path, base_path)
                except Exception:
                    relpath = file_path
                txt_file.write(f"Archivo: {relpath}\n")
                txt_file.write("Contenido:\n")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        txt_file.write(f.read())
                except Exception as e:
                    txt_file.write(f"Error al leer el archivo: {e}\n")
                txt_file.write("\n" + "=" * 40 + "\n\n")

print(f"Referencias generadas en: {output_root}")
