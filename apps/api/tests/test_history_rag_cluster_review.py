import pytest
from app.pipeline.history_rag_cluster_review import regroup


def test_shared_stimulus_and_uncertain_pairs_cannot_cross_splits():
    rows=[{'question_id':q,'page':i,'section_id':'1.1','group_id':f'pages:{i}',
           'page_exposed_in_prior_samples':i==3,'split':'test'} for i,q in enumerate('abcd',1)]
    manifest={'schema':'history-rag-question-clusters-v1','question_source_checksum':'s',
              'evidence_source_checksum':'e','seed':20261029,'questions':rows,
              'advisory_pairs_before_grouping':[{'question_ids':['a','b']},{'question_ids':['b','c']},
                                                {'question_ids':['c','d']}]}
    reviews={'schema':'history-rag-cluster-review-v1','question_source_checksum':'s',
             'pairs':[{'question_ids':['a','b'],'label':'shared_stimulus','reviewer':'ai'},
                      {'question_ids':['b','c'],'label':'uncertain','reviewer':'ai'},
                      {'question_ids':['c','d'],'label':'distinct_template','reviewer':'ai'}]}
    result=regroup(manifest,reviews);r={x['question_id']:x for x in result['questions']}
    assert r['a']['group_id']==r['b']['group_id']==r['c']['group_id']
    assert r['a']['split']==r['b']['split']==r['c']['split'] and r['a']['group_exposed']
    assert r['c']['group_id'] != r['d']['group_id']
    reviews['pairs'][0]['question_ids']=['a','d']
    with pytest.raises(ValueError,match='invalid review'):regroup(manifest,reviews)
