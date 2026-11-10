"""Tailored one-page resume for coordination/documentation roles, text only from facts.json."""
import sys
sys.path.insert(0,'../../scripts')
import compact_pdf
compact_pdf.T=34; compact_pdf.B=30
from compact_pdf import Sheet, header
from common import FACTS
def build(out, focus):
    f=FACTS; ident=f['identity']; e=f['eligibility']; c=f['capabilities']
    sh=Sheet(out); header(sh, ident)
    sh.text(f"{e['work_rights']}  ·  {e['drivers_licence']}  ·  {e['white_card']}", size=8.8, color=(0.35,0.35,0.35), gap=5)
    sh.heading('Professional profile', size=10.5)
    sh.text("Civil Engineering graduate (BSCE, Philippines) with an Australian Advanced Diploma of Civil Construction Design and practical site experience in the Philippines supporting construction delivery, site coordination and quality inspections. Experienced in reviewing structural and architectural drawings, maintaining progress and material records, and coordinating with engineers, subcontractors, suppliers and clients.", size=9.2, gap=4)
    sh.heading('Key capabilities', size=10.5)
    order={'coord':['project_coordination','technical_documentation','construction_support','civil_design']}[focus]
    lab={'project_coordination':'Project coordination','technical_documentation':'Technical documentation','construction_support':'Construction support','stakeholder_communication':'Stakeholder communication','civil_design':'Civil design'}
    sh.bullets([f"{lab[k]}: {c[k]}" for k in order]+[f"Software: {', '.join(c['software'])}"], size=8.8)
    sh.heading('Relevant experience', size=10.5)
    for x in f['experience'][:2]:
        sh.text(f"{x['role']}  ·  {x['employer']}  ·  {x['dates']}", font='hebo', size=9.4, gap=2)
        sh.bullets(x['points'][:4], size=8.8)
    sh.heading('Education', size=10.5)
    for x in f['education']:
        sh.text(f"{x['qualification']}  ·  {x['provider']}  ·  {x['dates']}", font='hebo', size=9.4, gap=2)
        sh.bullets(x['points'][:2], size=8.8)
    sh.heading('Additional experience and strengths', size=10.5)
    x=f['experience'][2]
    sh.text(x['role'].replace(' – ',', ')+f", {x['employer']}, {x['dates']}. Strengths: "+' · '.join(f['strengths'][:4])+'. References: '+f['references'].lower(), size=8.8, gap=2)
    sh.save()
if __name__=='__main__': build(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else 'coord')
