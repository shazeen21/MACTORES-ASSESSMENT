def test_start_run_end_to_end(client):
    task_resp = client.post(
        "/api/v1/tasks",
        json={
            "goal": "follow up with Acme",
            "scenario": "send_followup",
            "autonomy": "autonomous",
            "expected_effects": [{"tool": "send_message", "match": {"contact_id": "c_1"}}],
        },
    )
    task_id = task_resp.json()["id"]

    run_resp = client.post("/api/v1/runs", json={"task_id": task_id})

    assert run_resp.status_code == 201
    body = run_resp.json()
    assert body["status"] == "completed"
    assert body["verdict"]["passed"] is True


def test_start_run_404_for_missing_task(client):
    resp = client.post("/api/v1/runs", json={"task_id": "nope"})
    assert resp.status_code == 404