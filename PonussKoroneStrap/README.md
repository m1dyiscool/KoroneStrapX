# KoroneStrap

A lightweight bootstrapper/wrapper for **Korone Studio**, inspired by Bloxstrap.

---

## 📌 Requirements

Before you begin, make sure you have the following installed:

*   **[Python 3.x](https://www.python.org/downloads/)**
    > ⚠️ **Important:** During installation, ensure you check the box **"Add Python to PATH"**.
*   **Required Python Packages:** `colorama` and `pyinstaller`.

### Installing Dependencies

Open your terminal or command prompt and run:

```bash
pip install colorama pyinstaller
```

---

## 🛠️ Building from Source

Follow these steps to compile the project into a standalone executable:

### 1. Prepare the Environment
1. Download and extract the source code.
2. Place the project files into a folder of your choice (for example: `C:\Users\<Your_Username>\KoroneStrap`).

### 2. Compile the Executable
1. Open Command Prompt (`cmd`) and navigate to your project folder:
   ```cmd
   cd C:\Users\<Your_Username>\KoroneStrap
   ```
2. Run the following PyInstaller command to build the `.exe`:
   ```bash
   pyinstaller --noconfirm --onefile --windowed --add-data "486334643-c0477fe6-8ed3-48dc-9404-ff9463d542ca.jpg;." --add-data "icon.ico;." --icon "icon.ico" --name "KoroneStrap" "netstrap.py"
   ```

### 3. Locate the Output
Once the build process is complete, you can find your compiled `KoroneStrap.exe` in the newly created `dist` directory:
```text
C:\Users\<Your_Username>\KoroneStrap\dist\
```

---

## ⚙️ Customization

Feel free to fork this repository, modify the code, and adapt it to your needs!

---

## 💖 Support the Project

If you find this tool useful and want to support its development, you can purchase this shirt:

👉 **[Support Link](https://www.pekora.zip/catalog/9369/E)**