from platform_core.errors import problem_response


def test_problem_response_shape_is_rfc7807():
    """Cada campo de RFC 7807 debe estar presente (Seccion 2.6): nunca
    un {"error": "..."} ad-hoc."""
    resp = problem_response(404, "No encontrado", "El recurso no existe", "http://x/y")
    body = resp.body
    import json

    data = json.loads(body)
    assert set(data.keys()) == {"type", "title", "status", "detail", "instance"}
    assert data["status"] == 404
    assert resp.media_type == "application/problem+json"
