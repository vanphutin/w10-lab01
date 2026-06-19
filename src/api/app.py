# ==============================================================================
# FILE: src/api/app.py
# MỤC ĐÍCH: API Flask mẫu xuất Metrics cho Prometheus và giả lập tỉ lệ lỗi (ERROR_RATE) để test Canary Rollback.
#
# CÂU HỎI MENTOR CÓ THỂ HỎI:
# 1. Q: Endpoint `/metrics` sinh ra từ đâu và nó cung cấp những chỉ số nào?
#    A: Sinh ra từ thư viện `prometheus_flask_exporter`. Nó tự động đo lường số lượng request,
#       thời gian xử lý request, phân loại theo phương thức HTTP, endpoint, status code.
# 2. Q: Biến `ERROR_RATE` hoạt động ra sao và tại sao không được bật trong production?
#    A: Dùng hàm `random.random()` để lấy số ngẫu nhiên từ 0 đến 1. Nếu bé hơn `ERROR_RATE` thì ném lỗi 500.
#       Chỉ dùng để test rollback Canary. Production thực tế phải gỡ bỏ hoặc đặt bằng 0.
# ==============================================================================

import os
import random
from flask import Flask, jsonify
# Thư viện prometheus_flask_exporter giúp tự động hóa việc xuất các metrics HTTP của Flask
from prometheus_flask_exporter import PrometheusMetrics

# Khởi tạo ứng dụng web Flask
app = Flask(__name__)

# Khởi tạo PrometheusMetrics cho Flask app. 
# Dòng này tự động đăng ký endpoint `/metrics` để Prometheus Server có thể định kỳ scrape (cào) dữ liệu.
# Nó đo lường: số lượng request, thời gian phản hồi (duration), phân bố HTTP status (2xx, 3xx, 4xx, 5xx)...
PrometheusMetrics(app)

# Lấy tỉ lệ lỗi giả lập từ biến môi trường (Environment Variable), mặc định là 0 (0% lỗi)
# Giá trị này sẽ được ép kiểu về số thực (float) để thực hiện so sánh xác suất.
ERROR_RATE = float(os.getenv("ERROR_RATE", "0"))

# Lấy phiên bản của ứng dụng từ biến môi trường (ví dụ: v0.0.1, v0.0.2), mặc định là "v1"
VERSION = os.getenv("VERSION", "v1")

# Định nghĩa API Endpoint chính (Home path `/`) nhận yêu cầu GET
@app.get("/")
def index():
    # Giả lập lỗi ngẫu nhiên dựa trên ERROR_RATE.
    # random.random() trả về giá trị số thực ngẫu nhiên từ 0.0 đến 1.0.
    # Ví dụ: Nếu ERROR_RATE = 0.15 (15% lỗi), và random.random() trả về < 0.15, 
    # API sẽ trả về HTTP Status 500 (Internal Server Error) để giả lập lỗi hệ thống.
    if random.random() < ERROR_RATE:
        return jsonify(error="injected", version=VERSION), 500
    
    # Trả về HTTP 200 OK cùng thông tin phiên bản ứng dụng hiện tại
    return jsonify(ok=True, version=VERSION)

# Định nghĩa Endpoint kiểm tra sức khỏe (Health Check) phục vụ cho LivenessProbe và ReadinessProbe của Kubernetes
@app.get("/healthz")
def healthz():
    return "ok", 200

# Khởi chạy ứng dụng chạy trên tất cả các địa chỉ IP (0.0.0.0) tại cổng 8080 nếu chạy file trực tiếp
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

