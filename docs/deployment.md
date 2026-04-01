# 배포

## Docker Compose (권장)

```bash
docker compose up -d
```

- 8501: 웹 대시보드 (FastAPI)
- 8001: MCP 서버
- 스케줄러 내장: 매일 새벽 3시 데이터 수집 + 분석 자동 실행 (config.toml의 `schedule.data_update`)
- HTTP만 노출. 리버스 프록시/HTTPS/도메인은 별도 처리.

## 컨테이너 구성

하나의 컨테이너에서 2개 프로세스 실행:
1. MCP 서버 (백그라운드)
2. 웹 대시보드 - FastAPI (포그라운드, PID 1, 스케줄러 내장)

## 환경 변수 (.env)

프로젝트 루트에 `.env` 파일을 생성합니다. `.env.example`을 복사하여 사용.

```bash
cp .env.example .env
```

```
FRED_API_KEY=발급받은_키
FINNHUB_API_KEY=발급받은_키
```

Docker Compose가 `env_file: .env`로 자동 로딩합니다.

## config.toml 설정

가중치, 임계값 등 분석 파라미터를 관리합니다. API 키는 `.env`에서 관리.

```toml
[api_keys]
fred = ""  # .env의 FRED_API_KEY 사용
finnhub = ""  # .env의 FINNHUB_API_KEY 사용

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
real_rate = "REAINTRATREARAT10Y"
m2 = "M2SL"
gdp = "GDP"
treasury_10y = "DGS10"
treasury_3m = "DGS3MO"

[server]
web_port = 8501
mcp_port = 8001
mcp_host = "0.0.0.0"

[schedule]
data_update = "0 3 * * *"

[weights_gold]
real_rate = 0.30
m2_gold = 0.30
price_position = 0.20
return_10y = 0.20

[weights_silver]
real_rate = 0.25
m2_gold = 0.25
price_position = 0.15
return_10y = 0.15
gsr = 0.20

[weights_sp500]
cape = 0.35
buffett = 0.25
yield_curve = 0.15
return_10y = 0.25

[weights_ndx]
return_10y = 0.40
return_5y = 0.40
price_position = 0.20

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
- `8501`: 웹 대시보드 (FastAPI)
- `8001`: MCP 서버

외부에는 443(HTTPS) 하나만 노출하고, 경로 기반으로 내부 포트에 라우팅합니다.

### HAProxy 설정 예시

```haproxy
frontend https_front
    bind *:443 ssl crt /path/to/cert.pem

    acl padvisor     hdr(host) -i padvisor.example.com
    acl is_mcp       path_beg /mcp

    # /mcp 경로는 MCP 서버로, 나머지는 대시보드로
    use_backend padvisor_mcp if padvisor is_mcp
    use_backend padvisor     if padvisor

backend padvisor
    option httpchk
    compression algo gzip
    compression type text/html text/plain text/css application/javascript application/json
    http-check send meth GET uri /health ver HTTP/1.1 hdr Host padvisor.example.com
    http-check expect status 200
    balance roundrobin
    default-server inter 5s fastinter 3s rise 3 fall 3
    server web01 127.0.0.1:20012 check

backend padvisor_mcp
    option httpchk
    http-check send meth GET uri /health ver HTTP/1.1 hdr Host padvisor.example.com
    http-check expect status 200
    balance roundrobin
    default-server inter 5s fastinter 3s rise 3 fall 3
    server web01 127.0.0.1:20013 check
```

### Nginx 설정 예시

```nginx
server {
    listen 443 ssl;
    server_name padvisor.example.com;

    ssl_certificate     /etc/nginx/certs/cert.crt;
    ssl_certificate_key /etc/nginx/certs/cert.key;

    # MCP 서버
    location /mcp {
        proxy_pass http://127.0.0.1:20013;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # 대시보드
    location / {
        proxy_pass http://127.0.0.1:20012;
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

MCP 지원 AI 클라이언트 설정:

```json
{
  "mcpServers": {
    "portfolio-advisor": {
      "url": "https://portfolio.example.com/mcp"
    }
  }
}
```
