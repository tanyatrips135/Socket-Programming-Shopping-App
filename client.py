import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import json
import threading
import time
import argparse


class ServerConfigDialog(tk.Toplevel):
    def __init__(self, parent, default_host="127.0.0.1", default_port=9998):
        super().__init__(parent)
        self.title("Server Configuration")
        self.geometry("300x150")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = (default_host, default_port)

        ttk.Label(self, text="Server Host:").grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )
        self.host_entry = ttk.Entry(self, width=20)
        self.host_entry.insert(0, default_host)
        self.host_entry.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(self, text="Server Port:").grid(
            row=1, column=0, padx=10, pady=10, sticky="w"
        )
        self.port_entry = ttk.Entry(self, width=20)
        self.port_entry.insert(0, str(default_port))
        self.port_entry.grid(row=1, column=1, padx=10, pady=10)

        button_frame = ttk.Frame(self)
        button_frame.grid(row=2, column=0, columnspan=2, pady=15)

        ttk.Button(button_frame, text="Connect", command=self.on_connect).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(
            side=tk.LEFT, padx=10
        )

        self.center_window()
        self.wait_window(self)

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def on_connect(self):
        try:
            host = self.host_entry.get().strip()
            port = int(self.port_entry.get().strip())
            if not host:
                messagebox.showerror("Error", "Server host cannot be empty")
                return
            if port <= 0 or port > 65535:
                messagebox.showerror("Error", "Port must be between 1 and 65535")
                return
            self.result = (host, port)
            self.destroy()
        except ValueError:
            messagebox.showerror("Error", "Port must be a number")

    def on_cancel(self):
        self.result = None
        self.destroy()


class ShoppingClient:
    def __init__(self, server_host=None, server_port=None):
        self.root = tk.Tk()
        self.root.withdraw()
        self.client = None
        self.username = None
        self.cart = []
        self.products = []
        self.connected = False
        self.listener_thread = None
        self.server_host = server_host
        self.server_port = server_port

        if not self.server_host or not self.server_port:
            config = ServerConfigDialog(self.root)
            if config.result:
                self.server_host, self.server_port = config.result
            else:
                messagebox.showinfo(
                    "Cancelled", "Connection cancelled. Exiting application."
                )
                self.root.destroy()
                return

        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.server_host, self.server_port))
            self.connected = True
        except Exception as e:
            messagebox.showerror(
                "Connection Error",
                f"Failed to connect to {self.server_host}:{self.server_port}\n{e}",
            )
            return

        self.root.deiconify()
        self.root.title("Shopping App")
        self.root.geometry("900x600")
        self.root.state("zoomed")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.last_stock_update_time = time.time()

        self.setup_gui()
        self.listener_thread = threading.Thread(
            target=self.listen_for_broadcasts, daemon=True
        )
        self.listener_thread.start()
        self.root.mainloop()

    def connect_to_server(self):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.server_host, self.server_port))
            self.connected = True
            self.root.title(
                f"Shopping App - Connected to {self.server_host}:{self.server_port}"
            )

            self.listener_thread = threading.Thread(
                target=self.listen_for_broadcasts, daemon=True
            )
            self.listener_thread.start()

            return True
        except Exception as e:
            messagebox.showerror(
                "Connection Error",
                f"Could not connect to server at {self.server_host}:{self.server_port}\n\nError: {str(e)}",
            )
            return False

    def listen_for_broadcasts(self):
        while self.connected:
            try:
                response = self.client.recv(4096)
                if not response:
                    self.connected = False
                    self.root.after(0, self.show_reconnect_prompt)
                    break

                data = json.loads(response.decode("utf-8"))

                if data.get("action") == "stock_update":
                    self.root.after(0, lambda d=data: self.handle_stock_update(d))
                else:
                    self.response_data = data
                    self.response_received.set()
            except Exception as e:
                if self.connected:
                    print(f"Listener error: {str(e)}")
                    self.connected = False
                    self.root.after(0, self.show_reconnect_prompt)
                break

    def handle_stock_update(self, data):
        product_id = data.get("product_id")
        new_stock = data.get("new_stock")
        if product_id is None or new_stock is None:
            return
        self.last_stock_update_time = time.time()

        for i, product in enumerate(self.products):
            if product["id"] == product_id:
                self.products[i]["stock"] = new_stock
                break

        for item_id in self.products_tree.get_children():
            item = self.products_tree.item(item_id)
            values = item["values"]
            if values and values[0] == product_id:
                new_values = list(values)
                new_values[3] = new_stock
                self.products_tree.item(item_id, values=new_values)

                self.show_notification(
                    f"Product {values[1]} stock updated to {new_stock}"
                )
                break

    def show_notification(self, message):
        notification = tk.Toplevel(self.root)
        notification.overrideredirect(True)
        notification.attributes("-topmost", True)

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        notification_width = 300
        notification_height = 50
        x_position = screen_width - notification_width - 20
        y_position = screen_height - notification_height - 40

        notification.geometry(
            f"{notification_width}x{notification_height}+{x_position}+{y_position}"
        )

        frame = ttk.Frame(notification, style="Notification.TFrame")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=message, wraplength=280).pack(pady=10, padx=10)

        notification.after(3000, notification.destroy)

    def send_and_receive(self, data):
        if not self.connected:
            messagebox.showerror("Not Connected", "Not connected to server")
            return None

        self.response_received = threading.Event()
        self.response_data = None

        try:
            self.send(data)

            if self.response_received.wait(10.0):
                return self.response_data
            else:
                messagebox.showerror("Timeout", "Server response timeout")
                return None
        except Exception as e:
            messagebox.showerror("Communication Error", str(e))
            return None

    def send(self, data):
        try:
            if not self.client or not self.connected:
                raise ConnectionError("Not connected to server")
            self.client.sendall(json.dumps(data).encode("utf-8"))
        except Exception as e:
            self.connected = False
            raise e

    def receive(self):
        if self.response_data:
            data = self.response_data
            self.response_data = None
            return data
        return {}

    def setup_gui(self):
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

        self.status_var = tk.StringVar()
        self.status_var.set(f"Connected to {self.server_host}:{self.server_port}")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

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

        ttk.Button(frame, text="Add to Cart", command=self.add_selected_to_cart).pack(
            pady=10
        )

    def setup_cart_frame(self):
        frame = ttk.Frame(self.cart_frame, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Your Cart", font=("Arial", 16)).pack(pady=10)

        columns = ("id", "name", "quantity", "price")
        self.cart_tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col in columns:
            self.cart_tree.heading(col, text=col.capitalize())
        self.cart_tree.pack(fill=tk.BOTH, expand=True)

        self.total_label = ttk.Label(frame, text="Total: ₹0.00", font=("Arial", 12))
        self.total_label.pack(pady=5)

        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Checkout", command=self.handle_checkout).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            button_frame,
            text="Remove Selected Item",
            command=self.remove_selected_from_cart,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Cart", command=self.clear_cart).pack(
            side=tk.LEFT, padx=5
        )

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
        response = self.send_and_receive(
            {"action": "login", "username": username, "password": password}
        )

        if not response:
            return

        if response["status"] == "success":
            self.username = username
            self.notebook.tab(2, state="normal")
            self.notebook.tab(3, state="normal")
            self.notebook.tab(4, state="normal")
            self.load_products()
            self.load_history()
            self.notebook.select(2)
        else:
            messagebox.showerror(
                "Login Failed", response.get("message", "Unknown error")
            )

    def handle_register(self):
        username = self.reg_username.get()
        password = self.reg_password.get()
        response = self.send_and_receive(
            {"action": "register", "username": username, "password": password}
        )

        if not response:
            return

        if response["status"] == "success":
            messagebox.showinfo(
                "Registered", "Registration successful! You can now log in."
            )
        else:
            messagebox.showerror("Error", response.get("message", "Unknown error"))

    def load_products(self):
        response = self.send_and_receive({"action": "get_products"})
        if not response:
            return
        if response["status"] == "success":
            server_products = response["products"]
            recent_broadcast = (
                hasattr(self, "last_stock_update_time")
                and (time.time() - self.last_stock_update_time) < 5
            )
            if recent_broadcast:
                for server_product in server_products:
                    for local_product in self.products:
                        if local_product["id"] == server_product["id"]:
                            if local_product["stock"] != server_product["stock"]:
                                print(
                                    f"Stock discrepancy for {server_product['name']}: "
                                    f"Server:{server_product['stock']} Local:{local_product['stock']}"
                                )
                                server_product["stock"] = local_product["stock"]

            self.products = server_products

            for i in self.products_tree.get_children():
                self.products_tree.delete(i)

            for product in self.products:
                self.products_tree.insert(
                    "",
                    "end",
                    values=(
                        product["id"],
                        product["name"],
                        product["price"],
                        product["stock"],
                    ),
                )

            self.status_var.set(
                f"Connected to {self.server_host}:{self.server_port} - Products refreshed"
            )
            self.root.after(
                3000,
                lambda: self.status_var.set(
                    f"Connected to {self.server_host}:{self.server_port}"
                ),
            )

    def add_selected_to_cart(self):
        selected = self.products_tree.focus()
        if not selected:
            return
        item = self.products_tree.item(selected)["values"]
        product_id, name, price, stock = item
        quantity = simpledialog.askinteger(
            "Quantity", f"How many {name}s?", minvalue=1, maxvalue=stock
        )
        if quantity is None:
            return
        self.cart.append(
            {"id": product_id, "name": name, "price": price, "quantity": quantity}
        )
        self.update_cart_view()

    def update_cart_view(self):
        for i in self.cart_tree.get_children():
            self.cart_tree.delete(i)
        total = 0.0
        for item in self.cart:
            price = float(item["price"])
            quantity = int(item["quantity"])
            total += price * quantity
            self.cart_tree.insert(
                "", "end", values=(item["id"], item["name"], quantity, f"₹{price:.2f}")
            )
        self.total_label.config(text=f"Total: ₹{total:.2f}")

    def handle_checkout(self):
        if not self.cart:
            messagebox.showinfo("Empty Cart", "Your cart is empty!")
            return

        response = self.send_and_receive(
            {"action": "checkout", "username": self.username, "cart": self.cart}
        )

        if not response:
            return

        if response["status"] == "success":
            messagebox.showinfo(
                "Thank You!", "Your order has been placed successfully!"
            )
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
        if messagebox.askyesno(
            "Clear Cart", "Are you sure you want to clear your entire cart?"
        ):
            self.cart.clear()
            self.update_cart_view()

    def load_history(self):
        response = self.send_and_receive(
            {"action": "get_history", "username": self.username}
        )

        if not response:
            return

        if response["status"] == "success":
            for i in self.history_tree.get_children():
                self.history_tree.delete(i)
            for order in response["orders"]:
                self.history_tree.insert(
                    "",
                    "end",
                    values=(
                        order["id"],
                        order["product_id"],
                        order["product_name"],
                        order["quantity"],
                        order["order_time"],
                    ),
                )

    def show_reconnect_prompt(self):
        if not self.connected:
            popup = tk.Toplevel(self.root)
            popup.title("Disconnected")
            popup.geometry("300x150")
            popup.grab_set()
            popup.transient(self.root)

            ttk.Label(
                popup,
                text="Connection to server lost.\nDo you want to reconnect?",
                anchor="center",
                justify="center",
            ).pack(pady=20)

            button_frame = ttk.Frame(popup)
            button_frame.pack(pady=10)

            def attempt_reconnect():
                try:
                    self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.client.connect((self.server_host, self.server_port))
                    self.connected = True

                    self.listener_thread = threading.Thread(
                        target=self.listen_for_broadcasts, daemon=True
                    )
                    self.listener_thread.start()

                    popup.destroy()
                    messagebox.showinfo(
                        "Reconnected", "Connection re-established. Please log in again."
                    )

                    self.username = None
                    self.cart = []
                    self.notebook.select(self.login_frame)
                    self.notebook.tab(2, state="disabled")
                    self.notebook.tab(3, state="disabled")
                    self.notebook.tab(4, state="disabled")
                    self.status_var.set(
                        f"Connected to {self.server_host}:{self.server_port}"
                    )
                except Exception as e:
                    messagebox.showerror(
                        "Reconnect Failed", f"Could not reconnect:\n{e}"
                    )

            def try_different_server():
                popup.destroy()
                server_config = ServerConfigDialog(
                    self.root, self.server_host, self.server_port
                )
                if server_config.result:
                    self.server_host, self.server_port = server_config.result
                    attempt_reconnect()

            ttk.Button(button_frame, text="Reconnect", command=attempt_reconnect).pack(
                side=tk.LEFT, padx=5
            )
            ttk.Button(
                button_frame, text="Different Server", command=try_different_server
            ).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Exit", command=self.root.destroy).pack(
                side=tk.LEFT, padx=5
            )

    def on_closing(self):
        """Handle window closing event"""
        if self.connected:
            try:
                self.connected = False
                self.client.close()
            except:
                pass
        self.root.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shopping Client")
    parser.add_argument("--host", help="Server host address")
    parser.add_argument("--port", type=int, help="Server port")

    args = parser.parse_args()

    host = args.host if args.host else "127.0.0.1"
    port = args.port if args.port else 9998

    ShoppingClient(host, port)
