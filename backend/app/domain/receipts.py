"""Portable English EVE market-purchase parser and exact receipt arithmetic."""
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
import hashlib
import re

MAX_ISK = Decimal("9999999999999.99")
MAX_LINES = 5000
CENT = Decimal("0.01")


def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or amount > MAX_ISK or amount != amount.quantize(CENT):
        raise ValueError("Enter a non-negative ISK amount with at most two decimals (maximum 9,999,999,999,999.99)")
    return amount


def isk(value): return format(value.quantize(CENT), ".2f")


def amount(text, debit=False):
    text = text.strip().replace("\u00a0", " ")
    match = re.fullmatch(r"(-?)(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s+ISK", text)
    if not match or bool(match[1]) != debit:
        raise ValueError("Expected a purchase debit" if debit else "Expected a non-negative unit price in ISK")
    return money(match[2].replace(",", "") + ("." + match[3] if match[3] else ""))


def effective_unit_price(displayed, paid, quantity):
    if displayed * quantity == paid:
        return displayed, False
    # EVE can copy a whole-ISK/one-decimal display while keeping the exact
    # transaction debit. Only recover cent-exact prices consistent with that
    # displayed precision. Explicit two-decimal mismatches still fail.
    exponent = displayed.as_tuple().exponent
    unit_cents, remainder = divmod(int(paid * 100), quantity)
    effective = Decimal(unit_cents) * CENT
    if exponent > -2 and remainder == 0:
        quantum = Decimal(1).scaleb(exponent)
        if any(effective.quantize(quantum, rounding=mode) == displayed for mode in (ROUND_HALF_UP, ROUND_HALF_EVEN)):
            return effective, True
    raise ValueError("Quantity × unit price does not match the paid amount, and cannot be explained by displayed-price rounding")


def parse(text):
    if len(text) > 1_000_000: raise ValueError("Paste at most 1,000,000 characters")
    rows, seen, duplicates = [], {}, 0
    for source_line, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        if not raw.strip(): continue
        parts = raw.split("\t")
        if len(parts)==7 and parts[0].strip().casefold() in {"date", "date/time", "date / time"} and parts[1].strip().casefold() in {"quantity","qty"}: continue
        try:
            if len(parts) != 7: raise ValueError("Copy all seven tab-separated market transaction columns, not the wallet escrow journal")
            stamp, quantity, item, price, total, _seller, station = [p.strip() for p in parts]
            at = datetime.strptime(stamp, "%Y.%m.%d %H:%M")
            if not re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)", quantity): raise ValueError("Invalid whole-item quantity")
            qty = int(quantity.replace(",", ""))
            if not 1 <= qty <= 2147483647: raise ValueError("Quantity must be between 1 and 2,147,483,647")
            if not item or len(item) > 255 or len(station) > 500: raise ValueError("Item name or station is missing/too long")
            displayed, paid = amount(price), amount(total, debit=True)
            unit, rounded = effective_unit_price(displayed, paid, qty)
            signature = hashlib.sha256(raw.strip().encode()).hexdigest()
            duplicate_of = seen.get(signature)
            if duplicate_of: duplicates += 1
            else: seen[signature] = len(rows)+1
            rows.append({"id":len(rows)+1,"source_line":source_line,"purchased_at":at.isoformat()+"Z", "item":item,
                         "quantity":qty,"unit_price":isk(unit),"displayed_unit_price":isk(displayed),"unit_price_rounded":rounded,
                         "paid":isk(paid),"station":station,"duplicate_of":duplicate_of})
            if len(rows) > MAX_LINES: raise ValueError(f"Paste at most {MAX_LINES:,} purchase lines")
        except (ValueError, ArithmeticError) as error:
            raise ValueError(f"Line {source_line}: {error}") from error
    if not rows: raise ValueError("Paste at least one market purchase transaction")
    total = sum((Decimal(row["paid"]) for row in rows), Decimal(0))
    money(total)
    if len({row["item"].casefold() for row in rows}) > 1000: raise ValueError("Keep at most 1,000 different item types per receipt")
    warnings = [f"{duplicates} identical transaction line(s) retained. They may be separate purchases; review and exclude repeated paste lines if needed."] if duplicates else []
    rounded = sum(row["unit_price_rounded"] for row in rows)
    if rounded:
        warnings.append(f"{rounded} purchase line(s) have a rounded displayed unit price. Exact paid totals were retained and cent-exact unit prices recovered for exclusions.")
    return {"lines":rows,"purchase_total":isk(total),"transaction_count":len(rows),"duplicate_count":duplicates,"warnings":warnings}


def build(payload):
    parsed = parse(payload["text"])
    overrides = {int(key): value for key, value in payload.get("billable_quantities", {}).items()}
    if set(overrides) - {row["id"] for row in parsed["lines"]}: raise ValueError("An exclusion refers to a purchase line that is not in this paste; parse it again")
    groups, included, excluded = OrderedDict(), Decimal(0), Decimal(0)
    lines = []
    for source in parsed["lines"]:
        row = dict(source)
        billable = overrides.get(row["id"], row["quantity"])
        if type(billable) is not int or not 0 <= billable <= row["quantity"]: raise ValueError(f"Line {row['source_line']}: billable quantity must be between zero and the purchased quantity")
        # Allocate paid cents proportionally and round half-up, then derive the
        # exclusion as the remainder so charged + excluded always equals paid.
        numerator = int(Decimal(row["paid"])*100)*billable
        cents, remainder = divmod(numerator, row["quantity"])
        charged = Decimal(cents + (remainder*2 >= row["quantity"]))*CENT
        removed = Decimal(row["paid"])-charged
        included += charged; excluded += removed
        row.update(billable_quantity=billable,excluded_quantity=row["quantity"]-billable,charged=isk(charged),excluded=isk(removed))
        lines.append(row)
        group = groups.setdefault(row["item"].casefold(), {"item":row["item"],"purchased_quantity":0,"quantity":0,"excluded_quantity":0,"paid":Decimal(0),"charged":Decimal(0),"excluded":Decimal(0),"transactions":0})
        group["purchased_quantity"]+=row["quantity"];group["quantity"]+=billable;group["excluded_quantity"]+=row["quantity"]-billable
        group["paid"]+=Decimal(row["paid"]);group["charged"]+=charged;group["excluded"]+=removed;group["transactions"]+=1
    credit = money(payload.get("credit", 0))
    if credit and not payload.get("credit_reason", "").strip(): raise ValueError("Add a reason for the other exclusions / credit")
    hauling = money(payload.get("hauling_fee", 0))
    fuel, fuel_total = [], Decimal(0)
    for item in payload.get("fuel", []):
        quantity = item["quantity"]
        if type(quantity) is not int or quantity < 0: raise ValueError("Fuel quantity must be a non-negative whole number")
        cost = money(item["unit_price"])*quantity;money(cost)
        fuel_total += cost
        fuel.append({"item":item["item"].strip(),"quantity":quantity,"unit_price":isk(money(item["unit_price"])),"total":isk(cost)})
    if credit > included+hauling+fuel_total: raise ValueError("Other exclusions / credit cannot exceed items plus hauling and fuel")
    grand = money(included-credit+hauling+fuel_total)
    for group in groups.values():
        group["average_unit_price"] = isk((group["charged"]/group["quantity"]).quantize(CENT,rounding=ROUND_HALF_UP)) if group["quantity"] else None
        for field in ("paid","charged","excluded"):group[field]=isk(group[field])
    warnings = list(parsed["warnings"])
    for charge in fuel:
        if charge["quantity"] and (group := groups.get(charge["item"].casefold())) and group["quantity"]:
            warnings.append(f"{charge['item']} is charged both as purchased items and as fuel used. Review the billable quantities to avoid charging the same fuel twice.")
    return {"title":payload.get("title", "Market run receipt").strip() or "Market run receipt","recipient":payload.get("recipient", "").strip(),
            "note":payload.get("note", "").strip(),"groups":sorted(groups.values(), key=lambda r:r["item"].casefold()),"lines":lines,
            "warnings":warnings,"transaction_count":parsed["transaction_count"],"item_type_count":len(groups),
            "purchase_total":parsed["purchase_total"],"excluded_total":isk(excluded),"included_total":isk(included),
            "credit":isk(credit),"credit_reason":payload.get("credit_reason", "").strip(),"hauling_fee":isk(hauling),
            "fuel":fuel,"fuel_total":isk(fuel_total),"grand_total":isk(grand),"route":payload.get("route", {}),
            "purchase_from":min(row["purchased_at"] for row in lines),"purchase_to":max(row["purchased_at"] for row in lines)}
