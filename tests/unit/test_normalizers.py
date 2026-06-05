from tp_codex.normalizers import normalize_bug, normalize_history


def test_normalize_bug_supports_aliased_team_and_state_fields():
    record = normalize_bug(
        {
            "Id": 42,
            "Name": "Aliased bug",
            "team": "ESW UI Team",
            "state": "Ready for QA",
            "CreateDate": "2026-06-01T00:00:00+00:00",
            "Feature": [101, 202],
            "BugCategory": {"Name": "Regression"},
        },
        "https://example.tpondemand.com",
    )

    assert record["team"] == "ESW UI Team"
    assert record["status_raw"] == "Ready for QA"
    assert record["linked_feature_ids"] == [101, 202]


def test_normalize_bug_maps_review_export_business_fields():
    record = normalize_bug(
        {
            "Id": 101,
            "Name": "Crash on launch",
            "Suuntoappversion": "2.0.1",
            "Suuntoappplatform": "Android",
            "Products": [{"Name": "Watch A"}, {"Name": "Watch B"}],
            "Firmwareversion": "FW-9.8.7",
            "Reproducibility": {"Name": "Always"},
            "BugCategory": {"Name": "Regression"},
            "Feature": [{"Id": 501}, {"Id": 502}],
        },
        "https://example.tpondemand.com",
    )

    assert record["suunto_app_version"] == "2.0.1"
    assert record["suunto_app_platform"] == "Android"
    assert record["products"] == ["Watch A", "Watch B"]
    assert record["firmware_version"] == "FW-9.8.7"
    assert record["reproducibility"] == "Always"
    assert record["bug_category"] == "Regression"
    assert record["linked_feature_ids"] == [501, 502]


def test_normalize_bug_supports_v2_lowercase_reference_fields():
    record = normalize_bug(
        {
            "id": 211304,
            "name": "Live v2 bug",
            "createDate": "/Date(1780466008000+0200)/",
            "modifyDate": "/Date(1780466205000+0200)/",
            "lastStateChangeDate": "/Date(1780466008000+0200)/",
            "team": {"name": "ESW China NG3 Driver"},
            "project": {"name": "Suunto work"},
            "severity": {"name": "Critical"},
            "entityState": {"name": "New"},
            "owner": {"firstName": "Xiumin", "lastName": "Lin"},
            "products": {"items": [{"name": "Suunto Race 3"}]},
            "firmwareversion": "2.55.26",
            "feature": [{"id": 123}],
            "bugCategory": {"name": "Regression"},
            "reproducibility": {"name": "Always"},
            "suuntoappversion": "2.55.26",
            "suuntoappplatform": "Watch",
        },
        "https://example.tpondemand.com",
    )

    assert record["bug_id"] == 211304
    assert record["team"] == "ESW China NG3 Driver"
    assert record["project"] == "Suunto work"
    assert record["severity"] == "Critical"
    assert record["status_raw"] == "New"
    assert record["owner"] == "Xiumin Lin"
    assert record["products"] == ["Suunto Race 3"]
    assert record["firmware_version"] == "2.55.26"
    assert record["linked_feature_ids"] == [123]
    assert record["bug_category"] == "Regression"
    assert record["reproducibility"] == "Always"
    assert record["suunto_app_version"] == "2.55.26"
    assert record["suunto_app_platform"] == "Watch"


def test_normalize_history_supports_bug_simple_history_shape():
    events = normalize_history(
        [
            {
                "ResourceType": "BugSimpleHistory",
                "Id": 1477683,
                "Date": "/Date(1780657412097+0200)/",
                "EntityState": {"Name": "New"},
                "Modifier": {"FullName": "Lena Bergendahl"},
                "Project": {"Name": "Suunto work"},
                "Release": {"Name": "NG3 Release 1"},
                "Iteration": {"Name": "Sprint 24"},
                "Bug": {"Id": 211617, "Name": "Nautic update available banner placement"},
            }
        ]
    )

    assert events == [
        {
            "event_type": "state_snapshot",
            "changed_at": "/Date(1780657412097+0200)/",
            "field": "EntityState",
            "from": None,
            "to": "New",
            "modifier": "Lena Bergendahl",
            "release": "NG3 Release 1",
            "iteration": "Sprint 24",
            "project": "Suunto work",
        }
    ]
