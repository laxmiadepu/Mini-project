import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import csv
import sqlite3
import re

def infer_sqlite_type(values):
    """Infer SQLite type from multiple CSV values"""
    # Remove empty values
    non_empty = [str(v).strip() for v in values if v and str(v).strip() != ""]
    
    if not non_empty:
        return "TEXT"
    
    # Check if all are integers
    all_int = True
    all_float = True
    
    for val in non_empty:
        try:
            int(val)
        except:
            all_int = False
        
        try:
            float(val)
        except:
            all_float = False
    
    if all_int:
        return "INTEGER"
    elif all_float:
        return "REAL"
    else:
        return "TEXT"


def sanitize_table_name(name):
    """Sanitize table name to be SQLite compatible"""
    # Remove special characters, keep only alphanumeric and underscore
    name = re.sub(r'[^\w]', '_', name)
    # Ensure it doesn't start with a number
    if name and name[0].isdigit():
        name = 'table_' + name
    return name


def create_sqlite_from_csv(csv_path, db_path, table_name, replace_table=False):
    """Convert CSV to SQLite database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        with open(csv_path, "r", encoding="utf-8-sig") as file:  # utf-8-sig handles BOM
            reader = csv.reader(file)

            # Read headers
            headers = next(reader)
            headers = [h.strip() for h in headers]  # Strip whitespace
            
            if not headers:
                raise ValueError("CSV file has no headers")

            # Read sample rows for type inference
            sample_rows = []
            for _ in range(100):  # Sample first 100 rows
                try:
                    row = next(reader)
                    sample_rows.append(row)
                except StopIteration:
                    break
            
            if not sample_rows:
                raise ValueError("CSV file has no data rows")

            # Detect column types based on sample
            column_types = []
            for i in range(len(headers)):
                column_values = [row[i] if i < len(row) else "" for row in sample_rows]
                column_types.append(infer_sqlite_type(column_values))

            # Create column definitions
            columns_sql = ", ".join(
                f'"{headers[i]}" {column_types[i]}'
                for i in range(len(headers))
            )

            # Drop table if replace option is selected
            if replace_table:
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')

            # Create table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS "{table_name}" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {columns_sql}
                )
            """)

            # Prepare INSERT statement with quoted column names
            quoted_headers = [f'"{h}"' for h in headers]
            placeholders = ",".join("?" * len(headers))
            insert_sql = f'''
                INSERT INTO "{table_name}" ({",".join(quoted_headers)})
                VALUES ({placeholders})
            '''

            # Reset file pointer and skip header
            file.seek(0)
            next(reader)

            # Insert all rows with progress tracking
            row_count = 0
            for row in reader:
                # Pad row if it has fewer columns than headers
                while len(row) < len(headers):
                    row.append("")
                
                # Truncate row if it has more columns than headers
                row = row[:len(headers)]
                
                cursor.execute(insert_sql, row)
                row_count += 1

        conn.commit()
        return row_count

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def browse_csv():
    """Browse for CSV file"""
    file_path = filedialog.askopenfilename(
        title="Select CSV File",
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
    )
    if file_path:
        csv_var.set(file_path)
        # Auto-populate table name from filename
        if not table_var.get():
            filename = os.path.splitext(os.path.basename(file_path))[0]
            table_var.set(sanitize_table_name(filename))
        update_status("CSV file selected", "info")


def browse_db():
    """Browse for database location"""
    file_path = filedialog.asksaveasfilename(
        title="Save Database As",
        defaultextension=".db",
        filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
    )
    if file_path:
        db_var.set(file_path)


def update_status(message, status_type="info"):
    """Update status label"""
    colors = {
        "info": "#3498db",
        "success": "#27ae60",
        "error": "#e74c3c",
        "warning": "#f39c12"
    }
    status_label.config(text=message, foreground=colors.get(status_type, "black"))
    root.update()


def convert_to_sqlite():
    """Main conversion function"""
    csv_path = csv_var.get()
    table_name = table_var.get()
    db_path = db_var.get()

    # Validation
    if not csv_path:
        messagebox.showerror("Error", "Please select a CSV file")
        return
    
    if not os.path.exists(csv_path):
        messagebox.showerror("Error", "CSV file does not exist")
        return

    if not table_name:
        messagebox.showerror("Error", "Please enter a table name")
        return
    
    # Sanitize table name
    table_name = sanitize_table_name(table_name)
    table_var.set(table_name)

    if not db_path:
        db_path = os.path.join(os.path.dirname(csv_path), "database.db")
        db_var.set(db_path)

    try:
        update_status("Converting CSV to SQLite...", "info")
        convert_btn.config(state="disabled")
        root.update()

        replace = replace_var.get()
        row_count = create_sqlite_from_csv(csv_path, db_path, table_name, replace)

        update_status(f"Success! {row_count} rows imported", "success")
        
        messagebox.showinfo(
            "Conversion Complete",
            f"Database created successfully!\n\n"
            f"Location: {db_path}\n"
            f"Table: {table_name}\n"
            f"Rows imported: {row_count}"
        )
        
    except Exception as e:
        update_status("Conversion failed", "error")
        messagebox.showerror("Conversion Failed", f"Error: {str(e)}")
    
    finally:
        convert_btn.config(state="normal")


# ---------------- UI ----------------

root = tk.Tk()
root.title("CSV to SQLite Converter")
root.geometry("650x480")
root.resizable(False, False)
root.configure(bg="#f0f0f0")

# Variables
csv_var = tk.StringVar()
table_var = tk.StringVar()
db_var = tk.StringVar()
replace_var = tk.BooleanVar(value=False)

# Style
style = ttk.Style()
style.theme_use('clam')

# Header
header_frame = tk.Frame(root, bg="#2c3e50", height=70)
header_frame.pack(fill="x")
header_frame.pack_propagate(False)

title_label = tk.Label(
    header_frame,
    text="CSV to SQLite Converter",
    font=("Arial", 18, "bold"),
    bg="#2c3e50",
    fg="white"
)
title_label.pack(pady=20)

# Main container
main_frame = tk.Frame(root, bg="#f0f0f0")
main_frame.pack(fill="both", expand=True, padx=20, pady=20)

# CSV File Selection
csv_frame = tk.LabelFrame(main_frame, text="CSV File", font=("Arial", 10, "bold"), bg="#f0f0f0", pady=10, padx=10)
csv_frame.pack(fill="x", pady=(0, 10))

csv_entry = tk.Entry(csv_frame, textvariable=csv_var, width=55, font=("Arial", 10))
csv_entry.pack(side="left", padx=(0, 10))

browse_csv_btn = tk.Button(
    csv_frame,
    text="Browse",
    command=browse_csv,
    bg="#3498db",
    fg="white",
    font=("Arial", 10),
    width=10,
    cursor="hand2"
)
browse_csv_btn.pack(side="left")

# Database File Selection
db_frame = tk.LabelFrame(main_frame, text="Database Location (Optional)", font=("Arial", 10, "bold"), bg="#f0f0f0", pady=10, padx=10)
db_frame.pack(fill="x", pady=(0, 10))

db_entry = tk.Entry(db_frame, textvariable=db_var, width=55, font=("Arial", 10))
db_entry.pack(side="left", padx=(0, 10))

browse_db_btn = tk.Button(
    db_frame,
    text="Browse",
    command=browse_db,
    bg="#3498db",
    fg="white",
    font=("Arial", 10),
    width=10,
    cursor="hand2"
)
browse_db_btn.pack(side="left")

# Table Name
table_frame = tk.LabelFrame(main_frame, text="Table Name", font=("Arial", 10, "bold"), bg="#f0f0f0", pady=10, padx=10)
table_frame.pack(fill="x", pady=(0, 10))

table_entry = tk.Entry(table_frame, textvariable=table_var, width=40, font=("Arial", 10))
table_entry.pack()

# Options
options_frame = tk.LabelFrame(main_frame, text="Options", font=("Arial", 10, "bold"), bg="#f0f0f0", pady=10, padx=10)
options_frame.pack(fill="x", pady=(0, 10))

replace_check = tk.Checkbutton(
    options_frame,
    text="Replace table if it already exists",
    variable=replace_var,
    bg="#f0f0f0",
    font=("Arial", 9)
)
replace_check.pack(anchor="w")

# Convert Button
convert_btn = tk.Button(
    main_frame,
    text="Convert to SQLite",
    command=convert_to_sqlite,
    bg="#27ae60",
    fg="white",
    font=("Arial", 12, "bold"),
    width=20,
    height=2,
    cursor="hand2"
)
convert_btn.pack(pady=15)

# Status Label
status_label = tk.Label(
    main_frame,
    text="Ready to convert",
    font=("Arial", 9),
    bg="#f0f0f0",
    fg="#7f8c8d"
)
status_label.pack()

root.mainloop()