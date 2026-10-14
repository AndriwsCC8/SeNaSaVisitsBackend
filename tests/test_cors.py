from fastapi.testclient import TestClient

from main import app


def test_vite_development_origins_allow_authorized_json_preflight() -> None:
    client = TestClient(app)
    origins = (
        "http://localhost:8443",
        "https://localhost:8443",
        "http://127.0.0.1:8443",
        "https://127.0.0.1:8443",
    )

    for origin in origins:
        response = client.options(
            "/api/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert "authorization" in response.headers["access-control-allow-headers"].lower()
        assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_unlisted_cors_origin_remains_blocked() -> None:
    response = TestClient(app).options(
        "/api/auth/login",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers