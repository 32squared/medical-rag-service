FROM python:3.12-slim

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 전체 복사 (.dockerignore가 불필요 파일 제외)
COPY . .

# entrypoint 실행 권한 + CRLF 방어 (Windows에서 만들어졌을 가능성)
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# 로컬 실행 시 /data 폴백 디렉토리
RUN mkdir -p /data

# Cloud Run은 PORT 환경변수 사용
ENV PORT=8080
ENV DB_PATH=/data/app.db
ENV DATA_DIR=/data

EXPOSE 8080

# 기본 = RAG 서비스(rag_server.py). RUN_MODE=migrate 면 마이그레이션 1회 실행 (entrypoint.sh 참고)
ENV RUN_MODE=rag
ENTRYPOINT ["/app/entrypoint.sh"]
