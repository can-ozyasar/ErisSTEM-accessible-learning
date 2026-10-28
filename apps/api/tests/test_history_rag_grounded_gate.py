from app.pipeline.history_rag_grounded_gate import evaluate_case, valid_citation


def test_citation_requires_real_in_scope_verbatim_quote():
    evidence=[{'text':'Bu metin birinci kaynak içeriğidir.'}, {'text':'Başka bir gerçek kaynak metnidir.'}]
    assert valid_citation({'source':1,'quote':'birinci   kaynak içeriğidir'},evidence)
    assert not valid_citation({'source':2,'quote':'birinci kaynak içeriğidir'},evidence)
    assert not valid_citation({'source':True,'quote':'birinci kaynak içeriğidir'},evidence)
    assert not valid_citation({'source':1,'quote':'birinci kaynak değişik içeriğidir'},evidence)
    assert not valid_citation({'source':1,'quote':'metin'},evidence)


def test_gate_fails_closed_on_missing_fabricated_and_disagreeing_citations():
    case={'case_id':'q','choice_labels':['A','B'],'evidence':[{'text':'Bu metin birinci kaynak içeriğidir.'}]}
    citation={'source':1,'quote':'birinci kaynak içeriğidir'}
    gate={'decision':'sufficient','answer_label':'A','citation':citation}
    answer={'answer_label':'A','citation':citation,'explanation':'Kaynak bu bilgiyi içeriyor.'}
    assert evaluate_case(case,{'gate':gate,'answer':answer})['action']=='answer'
    assert evaluate_case(case,{'gate':gate,'answer':{**answer,'answer_label':'B'}})['action']=='abstain'
    assert evaluate_case(case,{'gate':{**gate,'citation':{'source':7,'quote':'birinci kaynak içeriğidir'}},'answer':answer})['action']=='abstain'
    assert evaluate_case(case,{'gate':None,'answer':answer})['action']=='abstain'
    assert evaluate_case({**case,'evidence':[]},{'gate':{'decision':'no_evidence'},'answer':None})['reason']=='no_evidence'
