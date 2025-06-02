from pytqshacl import infer as tqinfer, validate
from pathlib import Path
import tempfile
from rdflib import Graph, OWL


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
