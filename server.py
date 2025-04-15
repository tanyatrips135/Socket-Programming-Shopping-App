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
            "INSERT INTO products (name, price, stock) VALUES ('Apple', 1.2, 100), ('Banana', 0.5, 150)"
        )

    conn.commit()
    cursor.close()
    conn.close()


init_db()


def handle_client(client_socket):
    client_socket.settimeout(300)
    conn = mysql.connector.connect(
        user="shopping_user", password="shopping_password", database="shopping_app"
    )
    cursor = conn.cursor(dictionary=True)
    while True:
        try:
            data = client_socket.recv(4096)
            if not data:
                print("[SERVER] Client disconnected.")
                break
            request = json.loads(data.decode("utf-8"))
            action = request.get("action")
            print(f"[SERVER] Received: {action}")

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
                cursor.execute("SELECT * FROM products")
                products = cursor.fetchall()
                for product in products:
                    product["price"] = float(product["price"])
                    product["stock"] = int(product["stock"])

                send(client_socket, {"status": "success", "products": products})

            elif action == "checkout":
                username = request["username"]
                cart = request["cart"]
                cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
                user = cursor.fetchone()
                if not user:
                    send(
                        client_socket, {"status": "error", "message": "User not found"}
                    )
                    continue

                user_id = user["id"]
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
                            {"status": "error", "message": "Insufficient stock"},
                        )
                        break
                    cursor.execute(
                        "INSERT INTO orders (user_id, product_id, quantity) VALUES (%s, %s, %s)",
                        (user_id, product_id, quantity),
                    )
                    cursor.execute(
                        "UPDATE products SET stock = stock - %s WHERE id = %s",
                        (quantity, product_id),
                    )
                conn.commit()
                send(client_socket, {"status": "success"})

            elif action == "get_history":
                username = request["username"]
                cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
                user = cursor.fetchone()
                if not user:
                    send(
                        client_socket, {"status": "error", "message": "User not found"}
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

                # Convert the order_time from datetime to string (ISO 8601 format)
                for order in orders:
                    order["order_time"] = order[
                        "order_time"
                    ].isoformat()  # Convert to string format

                send(client_socket, {"status": "success", "orders": orders})

            else:
                send(client_socket, {"status": "error", "message": "Unknown action"})

        except socket.timeout:
            print("[SERVER] Client timed out.")
            break

        except Exception as e:
            print(f"[ERROR] {str(e)}")
            send(
                client_socket,
                {"status": "error", "message": f"Exception occurred: {str(e)}"},
            )
            break

    cursor.close()
    conn.close()
    client_socket.close()


def send(sock, data):
    try:
        sock.sendall(json.dumps(data).encode("utf-8"))
    except Exception as e:
        print(f"[SEND ERROR] {str(e)}")


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 9998))
    server.listen(5)
    print("[SERVER] Listening on port 9998")
    while True:
        client_sock, addr = server.accept()
        print(f"[SERVER] Connection from {addr}")
        threading.Thread(target=handle_client, args=(client_sock,)).start()


if __name__ == "__main__":
    start_server()
