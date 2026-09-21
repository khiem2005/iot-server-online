from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sqlite3
from urllib.parse import urlparse, parse_qs

# Tên file cơ sở dữ liệu SQLite
DB_NAME = "iot_server_data.db"
# Khóa bảo mật API
SECRET_KEY = "MY_SECRET_IOT_KEY_2026"


def init_db():
  """Khởi tạo bảng cơ sở dữ liệu nếu chưa tồn tại"""
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            temperature REAL,
            humidity REAL,
            led1 INTEGER,
            led2 INTEGER,
            led3 INTEGER
        )
    """)
  conn.commit()
  conn.close()


class IoTRequestHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    parsed_url = urlparse(self.path)
    path = parsed_url.path
    query_params = parse_qs(parsed_url.query)

    # 1. Endpoint xem giao diện biểu đồ
    if path == "/graph":
      self.send_response(200)
      self.send_header("Content-type", "text/html; charset=utf-8")
      self.end_headers()
      html_content = """
            <!DOCTYPE html>
            <html>
            <head><meta charset="utf-8"><title>IoT Dashboard</title></head>
            <body>
                <h2>IoT Sensor Dashboard & Chart</h2>
                <p>Hệ thống giám sát dữ liệu cảm biến IoT trực tuyến.</p>
            </body>
            </html>
            """
      self.wfile.write(html_content.encode("utf-8"))
      return

    # 2. Endpoint API lấy dữ liệu (GET)
    if path == "/api/data/get":
      api_key = query_params.get("api_key", [None])[0]
      if api_key != SECRET_KEY:
        self.send_response(401)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {"error": "Unauthorized: Sai hoặc thiếu api_key"}
            ).encode("utf-8")
        )
        return

      # Lấy các tham số lọc tùy chọn từ URL
      record_id = query_params.get("id", [None])[0]
      limit_str = query_params.get("limit", ["100"])[0]
      led1_str = query_params.get("led1", [None])[0]
      led2_str = query_params.get("led2", [None])[0]
      led3_str = query_params.get("led3", [None])[0]

      try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        query = (
            "SELECT id, device_id, timestamp, temperature, humidity, led1,"
            " led2, led3 FROM device_logs WHERE 1=1"
        )
        params = []

        # Lọc theo ID đơn lẻ chính xác
        if record_id:
          query += " AND id = ?"
          params.append(record_id)

        # Lọc theo trạng thái từng LED riêng lẻ
        if led1_str is not None:
          query += " AND led1 = ?"
          params.append(int(led1_str))
        if led2_str is not None:
          query += " AND led2 = ?"
          params.append(int(led2_str))
        if led3_str is not None:
          query += " AND led3 = ?"
          params.append(int(led3_str))

        query += " ORDER BY id DESC"

        if not record_id and limit_str:
          query += " LIMIT ?"
          params.append(int(limit_str))

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        data_list = []
        for r in rows:
          data_list.append({
              "_id": r[0],
              "device_id": r[1],
              "timestamp": r[2],
              "temperature": r[3],
              "humidity": r[4],
              "led_status": {"led1": r[5], "led2": r[6], "led3": r[7]},
          })

        response_data = {"total": len(data_list), "data": data_list}

        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            json.dumps(response_data, ensure_ascii=False).encode("utf-8")
        )

      except Exception as e:
        self.send_response(500)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
      return

    self.send_response(404)
    self.end_headers()
    self.wfile.write(b"Not Found")

  def do_POST(self):
    parsed_url = urlparse(self.path)
    path = parsed_url.path

    if path == "/api/data":
      content_length = int(self.headers.get("Content-Length", 0))
      post_data = self.wfile.read(content_length)

      try:
        payload = json.loads(post_data.decode("utf-8"))
        api_key = payload.get("api_key")

        if api_key != SECRET_KEY:
          self.send_response(401)
          self.send_header("Content-type", "application/json; charset=utf-8")
          self.end_headers()
          self.wfile.write(
              json.dumps(
                  {"error": "Unauthorized: Sai hoặc thiếu api_key"}
              ).encode("utf-8")
          )
          return

        device_id = payload.get("device_id", "Unknown_Device")
        timestamp = payload.get(
            "timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        temperature = payload.get("temperature", 0.0)
        humidity = payload.get("humidity", 0.0)
        led_status = payload.get("led_status", {})
        led1 = led_status.get("led1", 0)
        led2 = led_status.get("led2", 0)
        led3 = led_status.get("led3", 0)

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """
                INSERT INTO device_logs (device_id, timestamp, temperature, humidity, led1, led2, led3)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (device_id, timestamp, temperature, humidity, led1, led2, led3),
        )
        conn.commit()
        conn.close()

        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {"status": "success", "message": "Da luu du lieu vao CSDL"}
            ).encode("utf-8")
        )

      except Exception as e:
        self.send_response(500)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
      return

    self.send_response(404)
    self.end_headers()


def run_server():
  init_db()
  port = int(os.environ.get("PORT", 5000))
  server_address = ("0.0.0.0", port)
  httpd = HTTPServer(server_address, IoTRequestHandler)
  print(f"[*] IoT Server đang chạy và lắng nghe tại cổng {port}...")
  httpd.serve_forever()


if __name__ == "__main__":
  run_server()