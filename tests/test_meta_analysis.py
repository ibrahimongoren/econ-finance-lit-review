import json
import math

import pytest

np = pytest.importorskip("numpy")

import meta_analysis as m  # noqa: E402
from conftest import run  # noqa: E402
from litrev_common import FILES, HEADERS, write_csv  # noqa: E402


@pytest.mark.parametrize("t,df,expected", [
    # two-sided p-values of Student's t (reference values from SciPy)
    (2.0, 10, 0.07338803477074037),
    (1.96, 1000, 0.050273184955748736),
    (-3.7, 25, 0.0010659104948743106),
])
def test_t_pvalue(t, df, expected):
    assert m.t_pvalue(t, df) == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize("a,x,expected", [
    (1.0, 4.0, 0.018315638888734182),      # chi2 sf with df=2 at 8 -> exp(-4)
    (2.5, 3.0, 0.30621891841327875),
])
def test_gammaincc(a, x, expected):
    assert m.gammaincc(a, x) == pytest.approx(expected, rel=1e-9)


def test_random_effects_dl_hand_example():
    y, se = np.array([0.1, 0.3, 0.5]), np.array([0.1, 0.2, 0.1])
    fe = m.fixed_effect(y, se)
    re = m.random_effects_dl(y, se)
    assert fe["b"] == pytest.approx(0.3)
    assert re["Q"] == pytest.approx(8.0)
    assert re["tau2"] == pytest.approx(0.045)
    assert re["I2"] == pytest.approx(0.75)
    assert re["b"] == pytest.approx(0.3)
    assert re["Q_p"] == pytest.approx(math.exp(-4))


def test_wls_constant_equals_fixed_effect():
    rng = np.random.default_rng(0)
    se = rng.uniform(0.05, 0.4, 25)
    y = 0.2 + rng.normal(0, se)
    res = m.wls(y, np.ones((25, 1)), 1 / se ** 2)
    assert res["beta"][0] == pytest.approx(m.fixed_effect(y, se)["b"])


def test_wls_cluster_se_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(1)
    n = 60
    se = rng.uniform(0.05, 0.5, n)
    y = 0.2 + 1.0 * se + rng.normal(0, se)
    cl = rng.integers(0, 15, n)
    X = np.column_stack([np.ones(n), se])
    ours = m.wls(y, X, 1 / se ** 2, list(cl))
    ref = sm.WLS(y, X, weights=1 / se ** 2).fit(cov_type="cluster", cov_kwds={"groups": cl})
    assert np.allclose(ours["beta"], ref.params)
    assert np.allclose(ours["se_cl"], ref.bse)


def _simulate(selective: bool, seed: int = 4, true: float = 0.1, n_target: int = 300):
    rng = np.random.default_rng(seed)
    rows = []
    while len(rows) < n_target:
        se = rng.uniform(0.02, 0.5)
        est = true + rng.normal(0, se)
        if selective and est / se < 1.96 and rng.random() > 0.1:   # most insignificant results unpublished
            continue
        rows.append({"est_id": f"E{len(rows)}", "ref_id": f"S{len(rows) // 3}", "estimate": f"{est:.6f}",
                     "se": f"{se:.6f}", "include": "Y"})
    return rows


def test_pet_peese_recovers_effect_without_selection():
    rows, _ = m.prepare(_simulate(selective=False), pcc=False, moderators=[])
    res = m.analyse_group(rows, [], 0.10)
    assert res["pet_peese"]["estimate"]["b"] == pytest.approx(0.1, abs=0.03)
    assert res["fat"]["b1"]["p"] > 0.01


def test_pet_peese_reduces_bias_under_selection():
    rows, _ = m.prepare(_simulate(selective=True), pcc=False, moderators=[])
    res = m.analyse_group(rows, [], 0.10)
    corrected = res["pet_peese"]["estimate"]["b"]
    assert res["fat"]["b1"]["p"] < 0.01                     # asymmetry detected
    assert abs(corrected - 0.1) < abs(res["mean"] - 0.1)    # closer to the truth than the naive mean


def test_pcc_conversion_identity():
    rows, problems = m.prepare([{"est_id": "E1", "t": "2.5", "df": "100", "include": ""}], pcc=True, moderators=[])
    r = rows[0]
    assert not problems
    assert r["_y"] == pytest.approx(2.5 / math.sqrt(2.5 ** 2 + 100))
    assert r["_se"] == pytest.approx(r["_y"] / 2.5)          # se = r / t for partial correlations


def test_prepare_skips_and_reports_bad_rows():
    rows, problems = m.prepare([{"est_id": "E1", "estimate": "0.3", "se": ""},
                                {"est_id": "E2", "estimate": "0.3", "se": "0.1", "include": "N"},
                                {"est_id": "E3", "estimate": "0.3", "se": "0.1", "iv": "x"}],
                               pcc=False, moderators=["iv"])
    assert rows == []
    assert any("E1" in p for p in problems) and any("E3" in p for p in problems)


def test_cli_writes_summary_json_and_funnel(tmp_path):
    folder = tmp_path / "litrev-x"
    folder.mkdir()
    rows = _simulate(selective=True, n_target=60)
    for i, r in enumerate(rows):
        r["outcome"] = "lending" if i % 2 else "credit"
        r["iv"] = str(i % 2)
    header = HEADERS[FILES["estimates"]] + ["iv"]
    write_csv(folder / FILES["estimates"], rows, header)
    code, out = run("meta_analysis.py", folder, "--by", "outcome", "--moderators", "iv")
    assert code == 0, out
    meta = folder / FILES["meta_dir"]
    data = json.loads((meta / "meta_results.json").read_text(encoding="utf-8"))
    assert set(data["results"]) == {"lending", "credit"}
    assert "PET-PEESE" in (meta / "meta_summary.md").read_text(encoding="utf-8")
    if pytest.importorskip("matplotlib"):
        assert (meta / "funnel_lending.png").exists()
