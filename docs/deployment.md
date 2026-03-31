# 배포

## Docker Compose (권장)

```bash
docker compose up -d
```

- 8501: Streamlit 대시보드
- 8001: MCP 서버
- cron: 매일 새벽 3시 데이터 수집 + 분석 자동 실행
- HTTP만 노출. 리버스 프록시/HTTPS/도메인은 별도 처리.

## 컨테이너 구성

하나의 컨테이너에서 3개 프로세스 실행:
1. cron 데몬 (백그라운드)
2. MCP 서버 (백그라운드)
3. Streamlit (포그라운드, PID 1)

## 환경 변수 (.env)

프로젝트 루트에 `.env` 파일을 생성합니다. `.env.example`을 복사하여 사용.

```bash
cp .env.example .env
```

```
FRED_API_KEY=발급받은_키
```

Docker Compose가 `env_file: .env`로 자동 로딩합니다.

## config.toml 설정

가중치, 임계값 등 분석 파라미터를 관리합니다. API 키는 `.env`에서 관리.

```toml
[api_keys]
fred = ""  # .env의 FRED_API_KEY 사용

[data]
db_path = "data/portfolio.ddb"
raw_dir = "data/raw"
macrotrends_csv = "data/raw/silver_historical.csv"
shiller_excel = "data/raw/ie_data.xls"
shiller_url = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"

[symbols]
silver = "SI=F"
gold = "GC=F"
sp500 = "^GSPC"
ndx = "^NDX"
dxy = "DX-Y.NYB"
vix = "^VIX"

[fred_series]
fed_funds = "FEDFUNDS"
cpi = "CPIAUCSL"

[server]
streamlit_port = 8501
mcp_port = 8001
mcp_host = "0.0.0.0"

[schedule]
data_update = "0 3 * * *"

[weights]
w1_50y = 0.20
w2_10y = 0.25
w3_5y = 0.25
w4_valuation = 0.20
w5_gsr = 0.10

[signals]
strong_precious = -2.0
mild_precious = -1.0
mild_etf = 1.0
strong_etf = 2.0

[drawdown_overlay]
silver_crash_threshold = -40
etf_crash_threshold = -30
silver_rally_threshold = 100
```

## 리버스 프록시 설정 (HAProxy 예시)

Docker 컨테이너는 내부적으로 두 개의 포트를 사용합니다:
- `8501`: Streamlit 대시보드
- `8001`: MCP 서버

외부에는 443(HTTPS) 하나만 노출하고, 경로 기반으로 내부 포트에 라우팅합니다.

### HAProxy 설정 예시

```haproxy
frontend https_front
    bind *:443 ssl crt /etc/haproxy/certs/portfolio.pem

    # /mcp 경로는 MCP 서버로
    acl is_mcp path_beg /mcp
    use_backend mcp_back if is_mcp

    # 나머지는 대시보드로
    default_backend dashboard_back

backend dashboard_back
    server portfolio 127.0.0.1:8501 check

backend mcp_back
    server mcp 127.0.0.1:8001 check
```

### Nginx 설정 예시

```nginx
server {
    listen 443 ssl;
    server_name portfolio.example.com;

    ssl_certificate     /etc/nginx/certs/portfolio.crt;
    ssl_certificate_key /etc/nginx/certs/portfolio.key;

    # MCP 서버
    location /mcp {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # 대시보드
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 접속 확인

설정 후 접속:
- 대시보드: `https://portfolio.example.com`
- MCP: `https://portfolio.example.com/mcp`

## MCP 클라이언트 설정

Claude Desktop/Code에서:

```json
{
  "mcpServers": {
    "portfolio-advisor": {
      "url": "https://portfolio.example.com/mcp"
    }
  }
}
```
