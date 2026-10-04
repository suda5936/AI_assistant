"""T-11 (작성·검증): AC-18, AC-19, AC-20. 서비스 함수 직접 호출."""

import pytest
from board.errors import ValidationFailedError
from board.services import posts as ps
from conftest import T0


def _fields(exc_info):
    return [(d.field, d.message) for d in exc_info.value.details]


# ---------- AC-18 ----------
def test_ac18_create_sets_author_and_time(db, alice, snapshot):
    p = ps.create_post(db, alice, "제목", "내용\n둘째 줄", T0)
    assert p.id and p.author_id == alice.id and p.author.username == "alice"
    assert p.created_at == T0
    assert snapshot() == [(p.id, "제목", "내용\n둘째 줄", alice.id, "2026-10-03 01:00:00.000000")]


def test_ac18_value_is_not_stripped(db, alice):
    p = ps.create_post(db, alice, "  제목  ", "\n내용\n", T0)
    got = ps.get_post(db, p.id)
    assert got.title == "  제목  " and got.content == "\n내용\n"


def test_ac18_repeated_create_makes_distinct_posts(db, alice):
    a = ps.create_post(db, alice, "same", "same", T0)
    b = ps.create_post(db, alice, "same", "same", T0)
    assert a.id != b.id and ps.list_posts(db, 1).total == 2


def test_ac18_html_stored_verbatim(db, alice):
    t, c = "<script>alert(1)</script>", "<img src=x onerror=alert(1)>"
    p = ps.create_post(db, alice, t, c, T0)
    got = ps.get_post(db, p.id)
    assert (got.title, got.content) == (t, c)


# ---------- AC-19 ----------
@pytest.mark.parametrize("blank", ["", " ", "   ", "\n\t", "　", "　 \n"])
def test_ac19_blank_title_rejected(db, alice, snapshot, blank):
    with pytest.raises(ValidationFailedError) as e:
        ps.create_post(db, alice, blank, "내용", T0)
    assert _fields(e) == [("title", "제목을 입력해 주세요.")]
    assert snapshot() == []


@pytest.mark.parametrize("blank", ["", " ", "\n\t", "　"])
def test_ac19_blank_content_rejected(db, alice, snapshot, blank):
    with pytest.raises(ValidationFailedError) as e:
        ps.create_post(db, alice, "제목", blank, T0)
    assert _fields(e) == [("content", "내용을 입력해 주세요.")]
    assert snapshot() == []


def test_ac19_both_blank_title_first(db, alice):
    with pytest.raises(ValidationFailedError) as e:
        ps.create_post(db, alice, "", " ", T0)
    assert _fields(e) == [("title", "제목을 입력해 주세요."), ("content", "내용을 입력해 주세요.")]


# ---------- AC-20 ----------
def test_ac20_title_boundary(db, alice, snapshot):
    ok = ps.create_post(db, alice, "가" * 100, "c", T0)
    assert len(ps.get_post(db, ok.id).title) == 100
    with pytest.raises(ValidationFailedError) as e:
        ps.create_post(db, alice, "가" * 101, "c", T0)
    assert _fields(e) == [("title", "제목은 100자 이하여야 합니다.")]
    assert len(snapshot()) == 1


def test_ac20_content_boundary(db, alice, snapshot):
    ok = ps.create_post(db, alice, "t", "x" * 5000, T0)
    assert len(ps.get_post(db, ok.id).content) == 5000
    with pytest.raises(ValidationFailedError) as e:
        ps.create_post(db, alice, "t", "x" * 5001, T0)
    assert _fields(e) == [("content", "내용은 5000자 이하여야 합니다.")]
    assert len(snapshot()) == 1


def test_ac20_length_is_code_points_and_counts_whitespace(db, alice):
    ps.create_post(db, alice, "😀" * 100, "😀" * 5000, T0)
    with pytest.raises(ValidationFailedError):
        ps.create_post(db, alice, " " + "a" * 100, "c", T0)
    with pytest.raises(ValidationFailedError):
        ps.create_post(db, alice, "t", "a" * 5000 + "\n", T0)


def test_ac20_whitespace_only_101_is_blank_error(db, alice):
    with pytest.raises(ValidationFailedError) as e:
        ps.create_post(db, alice, " " * 101, "c", T0)
    assert _fields(e) == [("title", "제목을 입력해 주세요.")]


def test_ac20_both_too_long_two_errors(db, alice):
    with pytest.raises(ValidationFailedError) as e:
        ps.create_post(db, alice, "a" * 101, "b" * 5001, T0)
    assert [f for f, _ in _fields(e)] == ["title", "content"]


def test_ac20_lone_surrogate_rejected_not_crash(db, alice, snapshot):
    with pytest.raises(ValidationFailedError) as e:
        ps.create_post(db, alice, "a\ud800b", "c", T0)
    assert _fields(e) == [("title", "제목에 사용할 수 없는 문자가 포함되어 있습니다.")]
    with pytest.raises(ValidationFailedError) as e:
        ps.create_post(db, alice, "t", "a\udfffb", T0)
    assert _fields(e) == [("content", "내용에 사용할 수 없는 문자가 포함되어 있습니다.")]
    assert snapshot() == []
