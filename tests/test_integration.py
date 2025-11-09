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
FIXTURE_DIR = ROOT / "tests" / "fixtures"
DATA_FIXTURE = FIXTURE_DIR / "sample_building.ttl"
BRICK_FIXTURE = FIXTURE_DIR / "brick_rules.ttl"
SENSOR_SHAPES_FIXTURE = FIXTURE_DIR / "temperature_sensor_shape.ttl"

BRICK = Namespace("https://brickschema.org/schema/Brick#")
EX = Namespace("urn:example#")


def _temperature_sensor_shapes() -> Graph:
    shapes = Graph()
    shapes.parse(SENSOR_SHAPES_FIXTURE, format="turtle")
    return shapes


def _load_sample_graph() -> Graph:
    graph = Graph()
    graph.parse(DATA_FIXTURE, format="turtle")
    return graph


def _load_brick_rules() -> Graph:
    graph = Graph()
    graph.parse(BRICK_FIXTURE, format="turtle")
    return graph


def test_infer_adds_air_quality_type() -> None:
    data_graph = _load_sample_graph()
    brick_graph = _load_brick_rules()

    inferred_graph = infer(data_graph, brick_graph, min_iterations=1, max_iterations=2)

    assert (EX["co2_sensor"], RDF.type, BRICK.Air_Quality_Sensor) in inferred_graph
    assert (
        URIRef("urn:example"),
        OWL.imports,
        URIRef("urn:fixtures/brick_rules"),
    ) in inferred_graph


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
