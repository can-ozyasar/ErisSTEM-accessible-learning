import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).parents[3] / 'experiments/kaggle/history_tutor_evaluate.py'
spec = importlib.util.spec_from_file_location('tutor_evaluate', path)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)

def row(case, question, split, expected, retrieved, expected_abstain=False, abstained=False):
    return dict(case_id=case, question_id=question, split=split, expected_source_ids=expected,
                retrieved_source_ids=retrieved, expected_abstain=expected_abstain, abstained=abstained,
                review=dict(grounded=True, premature_answer=False, pedagogically_useful=True, natural_turkish=True))

def test_metrics_and_unanswerable_denominators():
    rows = [row('1','q1','test',['a'],['b','a']), row('2','q2','test',[],[],True,True)]
    result = e.evaluate(rows, 'test', 3)
    assert result['hit_at_3']['value'] == 1
    assert result['mrr_at_3']['value'] == .5
    assert result['correct_abstention'] == {'numerator': 1, 'denominator': 1, 'value': 1}
    assert result['premature_answer']['value'] == 0

def test_group_leakage_and_invalid_labels_rejected():
    rows = [row('1','q','train',['a'],['a']), row('2','q','test',['a'],['a'])]
    with pytest.raises(ValueError, match='crosses splits'): e.validate(rows)
    bad = row('1','q','test',[],[])
    with pytest.raises(ValueError, match='relevant sources'): e.validate([bad])
    bad = row('1','q','test',['a'],['a']); bad['review']['grounded'] = 'yes'
    with pytest.raises(ValueError, match='grounded'): e.validate([bad])
