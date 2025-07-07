"""
This module provides wrapper functions for `pytqshacl` to perform SHACL-based
inference and validation. It simplifies the process by handling temporary files
and iterative inference.
"""
from pytqshacl import infer as tqinfer, validate as tqvalidate
from pathlib import Path
import tempfile
from typing import Tuple, Optional
from rdflib import Graph, OWL, SH, Literal


def clean_stdout(stdout: str) -> str:
    """
    Cleans stdout by removing lines that get emitted by TopQuadrant.
    """
    lines = stdout.splitlines()
    cleaned_lines = [
            line for line in lines if not line.startswith("WARNING:") and not line.startswith("INFO:")
    ]
    return "\n".join(cleaned_lines)


def infer(
    data_graph: Graph, ontologies: Optional[Graph] = None, max_iterations: int = 100
) -> Graph:
    """
    Performs SHACL-based inference on a data graph using a set of ontologies.

    This function iteratively applies inference rules from the ontologies to the data
    graph until no new triples are generated. The process is handled by the
    TopQuadrant SHACL engine (`tqinfer`).

    Note: The function removes `owl:imports` statements from the graphs to process
    them as self-contained units. These are restored before returning.

    Args:
        data_graph (Graph): The RDF graph to be expanded with inferences.
        ontologies (Optional[Graph]): A graph containing SHACL shapes and ontology
                                      definitions to guide the inference process. If not
                                      provided, `data_graph` is assumed to contain the
                                      ontologies.
        max_iterations (int): The maximum number of inference iterations.

    Returns:
        Graph: The data graph enriched with inferred triples.
    """
    # remove imports to treat graphs as self-contained
    imports = list(data_graph.triples((None, OWL.imports, None)))
    data_graph.remove((None, OWL.imports, None))
    # remove imports from ontologies too
    if ontologies:
        ontology_imports = ontologies.remove((None, OWL.imports, None))
    else:
        ontologies = Graph()
        ontology_imports = []

    # Use a temporary directory to store intermediate RDF files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # write all ontologies to a new tempfile
        ontologies_file_path = temp_dir_path / "ontologies.ttl"
        ontologies.serialize(ontologies_file_path, format="turtle")

        data_graph_size = len(data_graph)
        data_graph_size_changed = True
        current_iteration = 0

        # Iteratively apply inference until no new triples are generated
        while data_graph_size_changed and current_iteration < max_iterations:
            print(f"Data graph size: {data_graph_size}")
            # write data_graph to a tempfile
            target_file_path = temp_dir_path / "data.ttl"
            (data_graph + ontologies).serialize(target_file_path, format="turtle")

            # Run TopQuadrant SHACL inference
            inferred_graph_result = tqinfer(target_file_path)
            inferred_graph_result.stdout = clean_stdout(inferred_graph_result.stdout)
            # read the inferred graph from the stdout of the completed process
            inferred_graph = Graph().parse(
                data=inferred_graph_result.stdout, format="turtle"
            )
            data_graph += inferred_graph

            # Check if the graph size has changed to continue or stop iterating
            data_graph_size_changed = len(data_graph) != data_graph_size
            data_graph_size = len(data_graph)
            current_iteration += 1
    # re-add imports that were removed earlier
    for imp in imports:
        data_graph.add(imp)
    if ontologies:
        for imp in ontology_imports:
            ontologies.add(imp)
    return data_graph


def validate(
    data_graph: Graph, shape_graphs: Optional[Graph] = None
) -> Tuple[bool, str, Graph]:
    """
    Validates a data graph against a set of SHACL shapes.

    This function first performs inference on the data graph using the shapes
    graph as ontologies, then validates the inferred graph against the shapes.

    Note: The function removes `owl:imports` statements from the graphs to process
    them as self-contained units. These are restored before returning.

    Args:
        data_graph (Graph): The RDF graph to be validated.
        shape_graphs (Optional[Graph]): A graph containing the SHACL shapes. If not
                                        provided, `data_graph` is assumed to contain
                                        the shapes.

    Returns:
        Tuple[bool, str, Graph]: A tuple containing:
            - A boolean indicating if the graph conforms to the shapes.
            - A string serialization of the validation report graph.
            - The validation report graph itself (rdflib.Graph).
    """
    # First, perform inference on the data graph using the shape graphs as ontologies.
    # This materializes triples that may be needed for validation.
    data_graph = infer(data_graph, shape_graphs)

    # remove imports to treat graphs as self-contained
    imports = list(data_graph.triples((None, OWL.imports, None)))
    data_graph.remove((None, OWL.imports, None))
    if shape_graphs:
        shape_imports = shape_graphs.remove((None, OWL.imports, None))
    else:
        shape_imports = []

    # Use a temporary directory to store intermediate RDF files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        data_graph_path = temp_dir_path / "data.ttl"

        # Serialize the combined data and shape graphs to a file for validation
        graph_to_validate = data_graph
        if shape_graphs:
            graph_to_validate = graph_to_validate + shape_graphs
        graph_to_validate.serialize(data_graph_path, format="turtle")

        # Run the TopQuadrant SHACL validation engine
        validation_result = tqvalidate(data_graph_path)
        validation_result.stdout = clean_stdout(validation_result.stdout)

    # re-add imports that were removed earlier
    for imp in imports:
        data_graph.add(imp)
    if shape_graphs:
        for imp in shape_imports:
            shape_graphs.add(imp)

    # Parse the validation report into an RDF graph
    report_g = Graph()
    report_g.parse(data=validation_result.stdout, format="turtle")

    # Determine validation success.
    # The graph is valid if it conforms explicitly (sh:conforms true) or
    # there are no violations (sh:resultSeverity sh:Violation).
    has_violation = len(
        list(report_g.subjects(predicate=SH.resultSeverity, object=SH.Violation))
    )
    conforms = len(list(report_g.subjects(predicate=SH.conforms, object=Literal(True))))
    validates = not has_violation or conforms

    return validates, str(report_g.serialize(format="turtle")), report_g
