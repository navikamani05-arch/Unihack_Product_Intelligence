import json, os, sys
from pathlib import Path
os.chdir('/home/ubuntu/ai-product-intelligence/backend')
sys.path.insert(0, '/home/ubuntu/ai-product-intelligence/backend')
import pandas as pd
from sqlalchemy import desc
from app.database import SessionLocal
from app.models.product import ProductRecord, ProductAttribute
from app.models.conflict import EvidenceChunk
from app.models.enrichment import EnrichmentRun
from app.models.commerce_output import CommerceOutput, CommerceOutputField
from app.services.official_ground_truth_service import profile_frame, comparable_columns, _attributes, _direct_generated, compare_values, identify_column

path='/home/ubuntu/upload/Unihack_ExpectedOutput-DeliveryFormat.csv'
frame=pd.read_csv(path, dtype=str, keep_default_na=False).fillna('')
ids=['PDSH4816AF','WDTS7024RZ']
db=SessionLocal()
identifier_column=identify_column(list(frame.columns))
profiles={p['name']:p for p in profile_frame(frame)}
comparison_columns=comparable_columns(frame)
for sku in ids:
    p=db.query(ProductRecord).filter(ProductRecord.sku==sku).first()
    print('\nPRODUCT',sku,'FOUND',bool(p))
    if not p: continue
    print('CORE',json.dumps({'id':p.id,'sku':p.sku,'name':p.name,'description':p.description,'manufacturer':p.manufacturer,'category':p.category},default=str))
    row=frame[frame[identifier_column]==sku].iloc[0]
    attrs_map=_attributes(p)
    print('COMPARABLE_FIELDS')
    for column in comparison_columns:
        if column == identifier_column: continue
        expected=str(row.get(column,''))
        if not expected.strip(): continue
        generated, mapped_field, evidence, reason = _direct_generated(p, attrs_map, column, row)
        print(json.dumps({'field':column,'expected':expected,'generated':generated,'mapped_field':mapped_field,'evidence':evidence,'reason':reason,'outcome':compare_values(expected,generated)},default=str))
    attrs=db.query(ProductAttribute).filter(ProductAttribute.product_id==p.id).all()
    print('ATTR_COUNT',len(attrs))
    for a in attrs:
        chunk=db.query(EvidenceChunk).filter(EvidenceChunk.stable_chunk_id==a.evidence_chunk_id).first() if a.evidence_chunk_id else None
        print('ATTR',json.dumps({'name':a.attribute_name,'raw':a.raw_value,'normalized':a.normalized_value,'unit':a.unit,'confidence':a.confidence_score,'source_type':a.source_type,'source_identifier':a.source_identifier,'source_url':a.source_url,'page_number':a.page_number,'row_number':a.row_number,'evidence_chunk_id':a.evidence_chunk_id,'evidence':chunk.snippet_text[:500] if chunk else None},default=str))
    er=db.query(EnrichmentRun).filter(EnrichmentRun.product_id==p.id).order_by(desc(EnrichmentRun.id)).first()
    print('ENRICHMENT',json.dumps({'id':er.id if er else None,'status':er.status if er else None,'output_snapshot':er.output_snapshot if er else None,'product_understanding':er.product_understanding if er else None,'missing_attributes':er.missing_attributes if er else None},default=str))
    co=db.query(CommerceOutput).filter(CommerceOutput.product_id==p.id).order_by(desc(CommerceOutput.id)).first()
    print('COMMERCE',json.dumps({'id':co.id if co else None,'record_snapshot':co.record_snapshot if co else None,'validation_summary':co.validation_summary if co else None},default=str))
    if co:
        fields=db.query(CommerceOutputField).filter(CommerceOutputField.commerce_output_id==co.id).all()
        for f in fields:
            print('CO_FIELD',json.dumps({'key':f.field_key,'display':f.display_name,'raw':f.raw_value,'normalized':f.normalized_value,'output':f.output_value,'unit':f.unit,'status':f.field_status,'validation':f.validation_status,'provenance':f.provenance_status,'evidence':f.evidence_snapshot},default=str))
print('\nOFFICIAL_ROWS')
for _,r in frame[frame['Mfg_Part_Num'].isin(ids)].iterrows():
    print(json.dumps({k:v for k,v in r.items() if v!=''},default=str))
