# Airflow Learning Setup

Cấu hình Airflow đơn giản cho việc học các DAG đơn giản với Docker Operations và Python Operations.

## 📋 Cấu trúc

- **docker-compose.yaml**: Chứa 3 service chính (PostgreSQL, Webserver, Scheduler)
- **dags/learning_dag.py**: Ví dụ DAG toàn bộ tính năng
- **.env.example**: Cấu hình mẫu

## 🚀 Cách khởi động

### 1. Chuẩn bị môi trường

```bash
# Sao chép file cấu hình mẫu
cp .env.example .env

# Tạo các thư mục cần thiết
mkdir -p dags logs config plugins

# Chi định User ID (Linux)
export AIRFLOW_UID=$(id -u)
```

### 2. Khởi động các container

```bash
# Khởi động tất cả services
docker-compose up -d

# Kiểm tra trạng thái
docker-compose ps
```

### 3. Truy cập Airflow

- **Web UI**: http://localhost:8080
- **Tài khoản mặc định**: 
  - Username: `airflow`
  - Password: `airflow`

## 📚 Ví dụ DAG

File `dags/learning_dag.py` chứa 4 tasks:

1. **python_task**: Python operation đơn giản
2. **process_task**: Xử lý dữ liệu từ task trước
3. **docker_task**: Chạy lệnh Ubuntu trong Docker
4. **python_docker_task**: Chạy Python script trong Docker container

### Sơ đồ dag:
```
python_task ──────────────> process_task
     │
     └──────> docker_task ──> python_docker_task
```

## ⚙️ Các lệnh hữu ích

```bash
# Xem logs của một service
docker-compose logs -f airflow-scheduler
docker-compose logs -f airflow-webserver

# Chạy một DAG thủ công
docker-compose exec airflow-scheduler airflow dags test learning_dag 2024-04-30

# Dừng các container
docker-compose down

# Dừng và xóa volume (reset database)
docker-compose down -v

# Rebuild images
docker-compose build
```

## 📝 Tạo DAG mới

Tạo file Python trong thư mục `dags/` với cấu trúc tương tự `learning_dag.py`:

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

default_args = {
    'owner': 'learning',
    'start_date': datetime(2024, 1, 1),
}

dag = DAG(
    'my_dag',
    default_args=default_args,
    schedule_interval='@daily',
)

def my_task():
    print("My task executed")

task = PythonOperator(
    task_id='my_python_task',
    python_callable=my_task,
    dag=dag,
)
```

## 🔧 Cài đặt thêm Python packages

Sửa trong file `.env`:
```
_PIP_ADDITIONAL_REQUIREMENTS=apache-airflow-providers-docker==3.8.0 requests==2.31.0
```

Sau đó rebuild containers:
```bash
docker-compose down
docker-compose build
docker-compose up -d
```

## ℹ️ Thông tin thêm

- **Executor**: LocalExecutor (phù hợp cho hoc tập và phát triển)
- **Database**: PostgreSQL 16
- **Python version**: 3.11

## 🛑 Xử lý sự cố

### Container không khởi động
```bash
docker-compose logs
docker-compose ps
```

### Xóa dữ liệu cũ
```bash
docker-compose down -v
docker-compose up -d
```

### Kiểm tra kết nối Docker
```bash
docker-compose exec airflow-scheduler docker ps
```

---

Selamat belajar! Happy Learning! 🎉

