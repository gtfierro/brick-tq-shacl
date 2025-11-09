"""End-to-end tests that exercise the public inference/validation APIs."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, SH

from brick_tq_shacl import infer, validate

JAVA_AVAILABLE = shutil.which("java") is not None

pytestmark = pytest.mark.skipif(
    not JAVA_AVAILABLE,
    reason="Java runtime is required for the TopQuadrant SHACL engine.",
)

ROOT = Path(__file__).resolve().parents[1]
DATA_FIXTURE = ROOT / "air_quality_sensor_example.ttl"
BRICK_FIXTURE = ROOT / "Brick.ttl"

BRICK = Namespace("https://brickschema.org/schema/Brick#")
EX = Namespace("urn:example#")

SENSOR_SHAPE_TTL = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix brick: <https://brickschema.org/schema/Brick#> .

brick:TemperatureSensorShape a sh:NodeShape ;
    sh:targetClass brick:Air_Temperature_Sensor ;
    sh:property [
        sh:path brick:hasUnit ;
        sh:minCount 1 ;
    ] .
"""


def _temperature_sensor_shapes() -> Graph:
    shapes = Graph()
    shapes.parse(data=SENSOR_SHAPE_TTL, format="turtle")
    return shapes


def _load_sample_graph() -> Graph:
    graph = Graph()
    graph.parse(DATA_FIXTURE, format="turtle")
    return graph


def test_validate_detects_missing_units() -> None:
    data_graph = _load_sample_graph()
    data_graph.remove((EX["air_temp_sensor"], BRICK.hasUnit, None))
    shapes = _temperature_sensor_shapes()

    validates, report_graph, report_text = validate(data_graph, shapes)

    assert not validates
    assert "Conforms: False" in report_text
    assert any(report_graph.subjects(SH.resultSeverity, SH.Violation))


def test_validate_passes_when_requirements_are_met() -> None:
    data_graph = _load_sample_graph()
    shapes = _temperature_sensor_shapes()

    validates, _, report_text = validate(data_graph, shapes)

    assert validates
    assert "Conforms: True" in report_text
