import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import json


class ShoppingClient:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(("127.0.0.1", 9998))
        self.username = None
        self.cart = []
        self.products = []

        self.setup_gui()
        self.root.mainloop()

    def send(self, data):
        try:
            self.client.sendall(json.dumps(data).encode("utf-8"))
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
            self.show_reconnect_prompt()
        except Exception as e:
            messagebox.showerror("Send Error", str(e))

    def receive(self):
        try:
            response = self.client.recv(4096)
            if not response:
                raise ConnectionResetError("Connection closed by server.")
            return json.loads(response.decode("utf-8"))
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
            self.show_reconnect_prompt()
            return {}
        except Exception as e:
            messagebox.showerror("Receive Error", str(e))
            return {}

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.state("zoomed")
        self.root.title("Shopping App")
        self.root.geometry("900x600")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.login_frame = ttk.Frame(self.notebook)
        self.register_frame = ttk.Frame(self.notebook)
        self.products_frame = ttk.Frame(self.notebook)
        self.cart_frame = ttk.Frame(self.notebook)
        self.history_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.login_frame, text="Login")
        self.notebook.add(self.register_frame, text="Register")
        self.notebook.add(self.products_frame, text="Products")
        self.notebook.add(self.cart_frame, text="Cart")
        self.notebook.add(self.history_frame, text="Order History")

        self.setup_login_frame()
        self.setup_register_frame()
        self.setup_products_frame()
        self.setup_cart_frame()
        self.setup_history_frame()

        self.notebook.tab(2, state="disabled")
        self.notebook.tab(3, state="disabled")
        self.notebook.tab(4, state="disabled")

    def setup_login_frame(self):
        frame = ttk.Frame(self.login_frame, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Login", font=("Arial", 16)).pack(pady=10)

        ttk.Label(frame, text="Username:").pack(pady=5, anchor="w")
        self.login_username = ttk.Entry(frame, width=30)
        self.login_username.pack(pady=5)

        ttk.Label(frame, text="Password:").pack(pady=5, anchor="w")
        self.login_password = ttk.Entry(frame, width=30, show="*")
        self.login_password.pack(pady=5)

        ttk.Button(frame, text="Login", command=self.handle_login).pack(pady=20)

    def setup_register_frame(self):
        frame = ttk.Frame(self.register_frame, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Register", font=("Arial", 16)).pack(pady=10)

        ttk.Label(frame, text="Username:").pack(pady=5, anchor="w")
        self.reg_username = ttk.Entry(frame, width=30)
        self.reg_username.pack(pady=5)

        ttk.Label(frame, text="Password:").pack(pady=5, anchor="w")
        self.reg_password = ttk.Entry(frame, width=30, show="*")
        self.reg_password.pack(pady=5)

        ttk.Button(frame, text="Register", command=self.handle_register).pack(pady=20)

    def setup_products_frame(self):
        frame = ttk.Frame(self.products_frame, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Products", font=("Arial", 16)).pack(pady=10)
        ttk.Button(frame, text="Refresh", command=self.load_products).pack(pady=5)

        columns = ("id", "name", "price", "stock")
        self.products_tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col in columns:
            self.products_tree.heading(col, text=col.capitalize())
        self.products_tree.pack(fill=tk.BOTH, expand=True)

        ttk.Button(frame, text="Add to Cart", command=self.add_selected_to_cart).pack(pady=10)

    def setup_cart_frame(self):
        frame = ttk.Frame(self.cart_frame, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Your Cart", font=("Arial", 16)).pack(pady=10)

        columns = ("id", "name", "quantity", "price")
        self.cart_tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col in columns:
            self.cart_tree.heading(col, text=col.capitalize())
        self.cart_tree.pack(fill=tk.BOTH, expand=True)

        self.total_label = ttk.Label(frame, text="Total: $0.00", font=("Arial", 12))
        self.total_label.pack(pady=5)

        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Checkout", command=self.handle_checkout).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Remove Selected Item", command=self.remove_selected_from_cart).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Cart", command=self.clear_cart).pack(side=tk.LEFT, padx=5)

    def setup_history_frame(self):
        frame = ttk.Frame(self.history_frame, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Order History", font=("Arial", 16)).pack(pady=10)

        columns = ("order_id", "product_id", "product_name", "quantity", "order_time")
        self.history_tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col in columns:
            self.history_tree.heading(col, text=col.replace("_", " ").capitalize())
        self.history_tree.pack(fill=tk.BOTH, expand=True)

    def handle_login(self):
        username = self.login_username.get()
        password = self.login_password.get()
        self.send({"action": "login", "username": username, "password": password})
        response = self.receive()
        if response["status"] == "success":
            self.username = username
            self.notebook.tab(2, state="normal")
            self.notebook.tab(3, state="normal")
            self.notebook.tab(4, state="normal")
            self.load_products()
            self.load_history()
            self.notebook.select(2)
        else:
            messagebox.showerror("Login Failed", response.get("message", "Unknown error"))

    def handle_register(self):
        username = self.reg_username.get()
        password = self.reg_password.get()
        self.send({"action": "register", "username": username, "password": password})
        response = self.receive()
        if response["status"] == "success":
            messagebox.showinfo("Registered", "Registration successful! You can now log in.")
        else:
            messagebox.showerror("Error", response.get("message", "Unknown error"))

    def load_products(self):
        self.send({"action": "get_products"})
        response = self.receive()
        if response["status"] == "success":
            self.products = response["products"]
            for i in self.products_tree.get_children():
                self.products_tree.delete(i)
            for product in self.products:
                self.products_tree.insert(
                    "", "end",
                    values=(product["id"], product["name"], product["price"], product["stock"])
                )

    def add_selected_to_cart(self):
        selected = self.products_tree.focus()
        if not selected:
            return
        item = self.products_tree.item(selected)["values"]
        product_id, name, price, stock = item
        quantity = simpledialog.askinteger("Quantity", f"How many {name}s?")
        if quantity is None:
            return
        self.cart.append({"id": product_id, "name": name, "price": price, "quantity": quantity})
        self.update_cart_view()

    def update_cart_view(self):
        for i in self.cart_tree.get_children():
            self.cart_tree.delete(i)
        total = 0.0
        for item in self.cart:
            price = float(item["price"])
            quantity = int(item["quantity"])
            total += price * quantity
            self.cart_tree.insert("", "end", values=(item["id"], item["name"], quantity, f"${price:.2f}"))
        self.total_label.config(text=f"Total: ${total:.2f}")

    def handle_checkout(self):
        self.send({"action": "checkout", "username": self.username, "cart": self.cart})
        response = self.receive()
        if response["status"] == "success":
            messagebox.showinfo("Thank You!", "Your order has been placed successfully!")
            self.cart.clear()
            self.update_cart_view()
            self.load_products()
            self.load_history()
            self.notebook.select(self.products_frame)
        else:
            messagebox.showerror("Error", response.get("message", "Unknown error"))

    def remove_selected_from_cart(self):
        selected = self.cart_tree.focus()
        if not selected:
            messagebox.showwarning("No Selection", "Please select an item to remove.")
            return

        item_values = self.cart_tree.item(selected)["values"]
        product_id = item_values[0]

        self.cart = [item for item in self.cart if item["id"] != product_id]
        self.update_cart_view()

    def clear_cart(self):
        if messagebox.askyesno("Clear Cart", "Are you sure you want to clear your entire cart?"):
            self.cart.clear()
            self.update_cart_view()

    def load_history(self):
        self.send({"action": "get_history", "username": self.username})
        response = self.receive()
        if response["status"] == "success":
            for i in self.history_tree.get_children():
                self.history_tree.delete(i)
            for order in response["orders"]:
                self.history_tree.insert(
                    "", "end",
                    values=(order["id"], order["product_id"], order["product_name"], order["quantity"], order["order_time"])
                )

    def show_reconnect_prompt(self):
        popup = tk.Toplevel()
        popup.title("Disconnected")
        popup.geometry("300x150")
        popup.grab_set()

        ttk.Label(popup, text="Server timed out.\nDo you want to reconnect?", anchor="center", justify="center").pack(pady=20)

        def attempt_reconnect():
            try:
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.connect(("127.0.0.1", 9998))
                popup.destroy()
                messagebox.showinfo("Reconnected", "Connection re-established. Please log in again.")
                self.notebook.select(self.login_frame)
                self.notebook.tab(2, state="disabled")
                self.notebook.tab(3, state="disabled")
                self.notebook.tab(4, state="disabled")
            except Exception as e:
                messagebox.showerror("Reconnect Failed", f"Could not reconnect:\n{e}")

        ttk.Button(popup, text="Reconnect", command=attempt_reconnect).pack(pady=10)

    def on_closing(self):
        self.client.close()
        self.root.destroy()


if __name__ == "__main__":
    ShoppingClient()
