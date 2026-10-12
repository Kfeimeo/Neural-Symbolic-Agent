"""Score a frozen chosen program on task test inputs, after synthesis ends."""
from ..arc.parse import parse
from ..arc.render import render
from ..language import base_library
from ..ml.parser import parse_term
from ..synthesis.evaluator import ERR, _CAUGHT, evaluate


def evaluate_test(record, test_pairs, extraction):
    text = record.get("expanded_program") or record.get("program")
    program = parse_term(text) if text else None
    library = base_library()
    rows = []
    for input_grid, expected in test_pairs:
        prediction = None
        if program is not None:
            scene = parse(input_grid, extraction)
            value = evaluate(program, library, (scene.objects,))
            if value is not ERR:
                try:
                    prediction = render(value, scene.grid_shape, scene.background)
                except _CAUGHT:
                    pass
        rows.append({"prediction": prediction, "correct": prediction == expected if expected is not None else None})
    labeled = [r for r in rows if r["correct"] is not None]
    return {"program_frozen_before_scoring": True, "num_test_pairs": len(rows),
            "labeled_pairs": len(labeled), "correct_pairs": sum(r["correct"] for r in labeled),
            "all_test_correct": all(r["correct"] for r in rows) if rows and len(labeled) == len(rows) else None,
            "pairs": rows}
