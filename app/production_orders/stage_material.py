# C7: stage-wise material rule. Har stage Start hone se pehle apna maal (recipe me us stage ke saamne wala, order line ka work_stage_id)
# store se poora issue (Posted) ho chuka hona chahiye. Order Start = sabse pehle stage ka maal poora (Melting: Tin / Lead).
# Baad ke stage (Flux / Spool / Box) ka maal partial issue ke saath order chalta hai, par wo stage tab tak start nahi hota — aur warning dikhti hai.
# Naya field nahi: order line me work_stage_id pehle se hai (product recipe se copy hota hai).
EPS = 0.00005


def posted_issued(line):
    # Is requirement line ka maal jo sach me production ke paas hai: sirf Posted issues (Draft se stock nahi hilta) minus wapas kiya hua
    total = 0.0
    for issue_line in line.issue_lines:
        issue = issue_line.issue
        if issue.is_deleted or issue.status != "Posted":
            continue
        total += issue_line.qty - issue_line.returned_qty
    return round(total, 4)


def stage_material_gap(order, work_stage_id):
    """Is work stage ke saamne wali order lines jinka poora maal abhi issue nahi hua. Wapas [{"name", "unit", "needed", "issued", "short"}].
    Bina work_stage_id wali purani lines ka koi stage-gate nahi (pehle jaisa chalta hai)."""
    gaps = []
    if not work_stage_id:
        return gaps
    for line in order.lines:
        if line.work_stage_id != work_stage_id:
            continue
        issued = posted_issued(line)
        if issued + EPS < line.required_qty:
            rm = line.raw_material
            gaps.append({"name": rm.name if rm else "Material", "unit": rm.base_unit.code if rm and rm.base_unit else "",
                         "needed": round(line.required_qty, 4), "issued": issued, "short": round(line.required_qty - issued, 4)})
    return gaps


def gap_text(gaps):
    # "500G Spool 150 of 200 PCS issued, Tin 40 of 60 KG issued"
    return ", ".join(f"{g['name']} {g['issued']:g} of {g['needed']:g} {g['unit']} issued".replace("  ", " ") for g in gaps)


def later_stage_gaps(order):
    """Order ke har stage ka (pehle stage ke baad wale) adhura issue: [(stage_name, gaps)]. Order list par red warning ke liye."""
    out = []
    for stage in list(order.stages)[1:]:
        if stage.status == "Done":
            continue
        gaps = stage_material_gap(order, stage.work_stage_id)
        if gaps:
            out.append((stage.stage_name, gaps))
    return out
