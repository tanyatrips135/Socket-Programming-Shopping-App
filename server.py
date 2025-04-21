import socket
import threading
import json
import mysql.connector


def init_db():
    conn = mysql.connector.connect(user="shopping_user", password="shopping_password")
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS shopping_app")
    cursor.execute("USE shopping_app")

    # Create users table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE,
            password VARCHAR(255)
        )
        """
    )

    # Create products table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255),
            price FLOAT,
            stock INT
        )
        """
    )

    # Create orders table with the order_time field
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            product_id INT,
            quantity INT,
            order_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """
    )

    # Insert some sample products if the table is empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO products (name, price, stock) VALUES ('Apple (1 kg)', 250, 100), ('Banana (1 kg)', 30, 150), ('Strawberry (200 gms)', 110, 150), ('Peach (500 gms)', 96, 150), ('Mango (1 kg)', 105, 150), ('Orange (1 kg)', 190, 150), ('Pineapple (1 pc)', 70, 150), ('Watermelon (1 pc)', 35, 150), ('Papaya (1 pc)', 70, 150)"
        )

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (id, username, password) VALUES (1, 'admin', '123456')"
        )

    conn.commit()
    cursor.close()
    conn.close()


init_db()

connected_clients = {}
clients_lock = threading.Lock()


def broadcast_stock_update(product_id, new_stock):
    update_message = {
        "action": "stock_update",
        "product_id": product_id,
        "new_stock": new_stock,
    }

    with clients_lock:
        disconnected_clients = []
        for client_id, client_socket in connected_clients.items():
            try:
                send(client_socket, update_message)
            except:
                disconnected_clients.append(client_id)

        for client_id in disconnected_clients:
            del connected_clients[client_id]


def handle_client(client_socket, client_address):
    client_id = f"{client_address[0]}:{client_address[1]}"

    with clients_lock:
        connected_clients[client_id] = client_socket

    client_socket.settimeout(300)

    conn = mysql.connector.connect(
        user="shopping_user", password="shopping_password", database="shopping_app"
    )
    cursor = conn.cursor(dictionary=True)

    try:
        while True:
            try:
                data = client_socket.recv(4096)
                if not data:
                    print(f"[SERVER] Client {client_id} disconnected.")
                    break

                request = json.loads(data.decode("utf-8"))
                action = request.get("action")
                print(f"[SERVER] Received from {client_id}: {action}")

                if action == "register":
                    username = request["username"]
                    password = request["password"]
                    try:
                        cursor.execute(
                            "INSERT INTO users (username, password) VALUES (%s, %s)",
                            (username, password),
                        )
                        conn.commit()
                        send(client_socket, {"status": "success"})
                    except mysql.connector.errors.IntegrityError:
                        send(
                            client_socket,
                            {"status": "error", "message": "Username already exists"},
                        )

                elif action == "login":
                    username = request["username"]
                    password = request["password"]
                    cursor.execute(
                        "SELECT * FROM users WHERE username=%s AND password=%s",
                        (username, password),
                    )
                    if cursor.fetchone():
                        send(client_socket, {"status": "success"})
                    else:
                        send(
                            client_socket,
                            {"status": "error", "message": "Invalid credentials"},
                        )

                elif action == "get_products":
                    conn.commit()
                    cursor.execute("SELECT * FROM products")
                    products = cursor.fetchall()
                    for product in products:
                        product["price"] = float(product["price"])
                        product["stock"] = int(product["stock"])

                    send(client_socket, {"status": "success", "products": products})

                elif action == "checkout":
                    username = request["username"]
                    cart = request["cart"]
                    cursor.execute(
                        "SELECT id FROM users WHERE username=%s", (username,)
                    )
                    user = cursor.fetchone()
                    if not user:
                        send(
                            client_socket,
                            {"status": "error", "message": "User not found"},
                        )
                        continue

                    user_id = user["id"]
                    updated_products = []

                    valid_order = True
                    for item in cart:
                        product_id = item["id"]
                        quantity = item["quantity"]

                        cursor.execute(
                            "SELECT stock FROM products WHERE id=%s", (product_id,)
                        )
                        product = cursor.fetchone()
                        if not product or product["stock"] < quantity:
                            send(
                                client_socket,
                                {
                                    "status": "error",
                                    "message": f"Insufficient stock for product ID {product_id}",
                                },
                            )
                            valid_order = False
                            break

                    if not valid_order:
                        continue

                    for item in cart:
                        product_id = item["id"]
                        quantity = item["quantity"]

                        cursor.execute(
                            "INSERT INTO orders (user_id, product_id, quantity) VALUES (%s, %s, %s)",
                            (user_id, product_id, quantity),
                        )

                        cursor.execute(
                            "UPDATE products SET stock = stock - %s WHERE id = %s",
                            (quantity, product_id),
                        )

                        cursor.execute(
                            "SELECT stock FROM products WHERE id=%s", (product_id,)
                        )
                        new_stock = cursor.fetchone()["stock"]
                        updated_products.append((product_id, new_stock))

                    conn.commit()
                    send(client_socket, {"status": "success"})

                    for product_id, new_stock in updated_products:
                        broadcast_stock_update(product_id, new_stock)

                elif action == "get_history":
                    username = request["username"]
                    cursor.execute(
                        "SELECT id FROM users WHERE username=%s", (username,)
                    )
                    user = cursor.fetchone()
                    if not user:
                        send(
                            client_socket,
                            {"status": "error", "message": "User not found"},
                        )
                        continue

                    user_id = user["id"]
                    cursor.execute(
                        """
                        SELECT orders.id, orders.product_id, orders.quantity, orders.order_time, products.name AS product_name
                        FROM orders
                        JOIN products ON orders.product_id = products.id
                        WHERE orders.user_id = %s
                        """,
                        (user_id,),
                    )
                    orders = cursor.fetchall()

                    for order in orders:
                        order["order_time"] = order["order_time"].isoformat()

                    send(client_socket, {"status": "success", "orders": orders})

                else:
                    send(
                        client_socket, {"status": "error", "message": "Unknown action"}
                    )

            except socket.timeout:
                print(f"[SERVER] Client {client_id} timed out.")
                break

            except json.JSONDecodeError:
                print(f"[SERVER] Invalid JSON from client {client_id}")
                send(
                    client_socket, {"status": "error", "message": "Invalid JSON format"}
                )

            except Exception as e:
                print(f"[ERROR] {str(e)}")
                try:
                    send(
                        client_socket,
                        {"status": "error", "message": f"Exception occurred: {str(e)}"},
                    )
                except:
                    pass
                break

    finally:

        cursor.close()
        conn.close()

        with clients_lock:
            if client_id in connected_clients:
                del connected_clients[client_id]

        try:
            client_socket.close()
        except:
            pass


def send(sock, data):
    try:
        sock.sendall(json.dumps(data).encode("utf-8"))
    except Exception as e:
        print(f"[SEND ERROR] {str(e)}")
        raise


def start_server(host="0.0.0.0", port=9998):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    print(f"[SERVER] Listening on {host}:{port}")

    try:
        while True:
            client_sock, addr = server.accept()
            print(f"[SERVER] Connection from {addr}")
            threading.Thread(target=handle_client, args=(client_sock, addr)).start()
    except KeyboardInterrupt:
        print("[SERVER] Shutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Shopping App Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind to")
    parser.add_argument("--port", type=int, default=9998, help="Port to listen on")

    args = parser.parse_args()

    start_server(args.host, args.port)
