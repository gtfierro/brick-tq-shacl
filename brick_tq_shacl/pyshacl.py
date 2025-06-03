from pytqshacl import infer as tqinfer, validate as tqvalidate
from pathlib import Path
import tempfile
from rdflib import Graph, OWL, SH, Literal


def infer(
    data_graph: Graph, ontologies: Graph, max_iterations: int = 100
):
    # remove imports
    imports = list(data_graph.triples((None, OWL.imports, None)))
    data_graph.remove((None, OWL.imports, None))
    # remove imports from ontologies too
    ontologies.remove((None, OWL.imports, None))

    # write data_graph to a tempfile, write all ontologies to a new tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # write all ontologies to a new tempfile
        ontologies_file_path = temp_dir_path / "ontologies.ttl"
        ontologies.serialize(ontologies_file_path, format="turtle")

        data_graph_size = len(data_graph)
        data_graph_size_changed = True

        while data_graph_size_changed:
            # write data_graph to a tempfile
            target_file_path = temp_dir_path / "data.ttl"
            data_graph.serialize(target_file_path, format="turtle")

            inferred_graph = tqinfer(target_file_path, shapes=ontologies_file_path)
            # read the inferred graph
            inferred_graph = Graph().parse(data=inferred_graph.stdout, format="turtle")
            data_graph += inferred_graph
            data_graph_size_changed = len(data_graph) != data_graph_size
            data_graph_size = len(data_graph)
    # re-add imports
    for imp in imports:
        data_graph.add(imp)
    return data_graph.de_skolemize()


def validate(
    data_graph: Graph, shape_graphs: Graph
    ):
    # infer the data graph
    data_graph = infer(data_graph, shape_graphs)

    imports = list(data_graph.triples((None, OWL.imports, None)))
    data_graph.remove((None, OWL.imports, None))
    shape_graphs.remove((None, OWL.imports, None))

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        # Define the target path within the temporary directory
        data_graph_path = temp_dir_path / "data.ttl"
        shape_graphs_path = temp_dir_path / "shapes.ttl"

        # Serialize the graphs to files
        data_graph.serialize(data_graph_path, format="turtle")
        shape_graphs.serialize(shape_graphs_path, format="turtle")

        # Run the pytqshacl_validate function
        validation_result = tqvalidate(data_graph_path, shapes=shape_graphs_path)
        print(validation_result.stdout)
        # Parse the validation result into a graph
    # re-add imports
    for imp in imports:
        data_graph.add(imp)
    report_g = Graph()
    report_g.parse(data=validation_result.stdout, format="turtle")

    # Check if there are any sh:resultSeverity sh:Violation predicate/object pairs
    has_violation = len(
        list(report_g.subjects(predicate=SH.resultSeverity, object=SH.Violation))
    )
    conforms = len(
        list(report_g.subjects(predicate=SH.conforms, object=Literal(True)))
    )
    validates = not has_violation or conforms

    return validates, str(report_g.serialize(format="turtle")), report_g
