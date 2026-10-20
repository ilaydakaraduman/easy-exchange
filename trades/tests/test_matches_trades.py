import re

from django.test import TestCase, override_settings

from catalog.models import Category, Item
from trades.models import Match, Trade
from trades.services import accept_trade, cancel_trade, propose_trade, reject_trade
from trades.tests.test_propose import make_item, make_user, match_items


def _match_id(left, right):
    low, high = sorted((left.id, right.id))
    return Match.objects.get(item_a_id=low, item_b_id=high).id


def _trade_sections(html):
    start = html.index('<div class="matches_trades">')
    block = html[start:]
    incoming_at = block.index("Incoming proposals")
    outgoing_at = block.index("Outgoing proposals")
    finished_at = block.index("Finished trades")
    return (
        block[incoming_at:outgoing_at],
        block[outgoing_at:finished_at],
        block[finished_at:],
    )


def _listing_card(html, title):
    for part in html.split('<li class="listing-card">')[1:]:
        card = part.split("</li>", 1)[0]
        if title in card:
            return card
    raise AssertionError(f"{title} is missing from the browse page")


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class MatchesTradeSectionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            slug="funko",
            name="Funko Pop & Figures",
            metadata_schema=[],
        )
        self.user_a = make_user("a@example.com", "User A")
        self.user_b = make_user("b@example.com", "User B")
        self.user_c = make_user("c@example.com", "User C")
        self.item_x = make_item(self.user_a, self.category, "Item X")
        self.item_y = make_item(self.user_b, self.category, "Item Y")
        self.item_z = make_item(self.user_c, self.category, "Item Z")

    def _page(self, user):
        self.client.force_login(user)
        response = self.client.get("/matches")
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _propose(self):
        match_items(self.item_x, self.item_y)
        return propose_trade(self.user_a, self.item_x, self.item_y)

    def test_propose_button_when_both_items_are_available(self):
        """Spec 06 case 27: both AVAILABLE items show a Propose trade form."""
        match_items(self.item_x, self.item_y)
        match_id = _match_id(self.item_x, self.item_y)

        html = self._page(self.user_a)

        form = re.search(
            rf'<form method="post" action="/matches/{match_id}/propose">(.*?)</form>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(form)
        self.assertIn('name="csrfmiddlewaretoken"', form.group(1))
        self.assertIn(">Propose trade</button>", form.group(1))

    def test_no_propose_button_when_an_item_is_in_trade(self):
        """Spec 06 case 27: an IN_TRADE item hides the Propose trade control."""
        match_items(self.item_x, self.item_y)
        self.item_x.status = Item.Status.IN_TRADE
        self.item_x.save(update_fields=["status"])

        html = self._page(self.user_a)

        self.assertNotIn("Propose trade", html)
        self.assertNotIn("/propose", html)

    def test_no_propose_button_when_an_item_is_traded(self):
        """Spec 06 case 27: a TRADED item hides the Propose trade control."""
        match_items(self.item_x, self.item_y)
        self.item_y.status = Item.Status.TRADED
        self.item_y.save(update_fields=["status"])

        html = self._page(self.user_a)

        self.assertNotIn("Propose trade", html)
        self.assertNotIn("/propose", html)

    def test_only_the_proposable_match_has_a_propose_form(self):
        """Spec 06 case 27: two matches render exactly one form, for the open pair."""
        match_items(self.item_x, self.item_z)
        match_items(self.item_x, self.item_y)
        self.item_z.status = Item.Status.TRADED
        self.item_z.save(update_fields=["status"])
        live_id = _match_id(self.item_x, self.item_y)

        html = self._page(self.user_a)

        forms = re.findall(r'action="(/matches/\d+/propose)"', html)
        self.assertEqual(forms, [f"/matches/{live_id}/propose"])

    def test_incoming_proposal_rendered_for_the_counterparty(self):
        """Spec 06 case 28: the counterparty sees the trade under Incoming proposals."""
        trade = self._propose()

        html = self._page(self.user_b)

        self.assertLess(html.index('class="match-row"'), html.index("Incoming proposals"))
        self.assertLess(html.index("Incoming proposals"), html.index("Outgoing proposals"))
        self.assertLess(html.index("Outgoing proposals"), html.index("Finished trades"))
        incoming, outgoing, finished = _trade_sections(html)
        your, their = incoming.split("Their item", 1)
        self.assertIn(self.item_y.title, your)
        self.assertIn(f'href="/listings/{self.item_y.id}"', your)
        self.assertIn(">IN_TRADE</span>", your)
        self.assertIn(self.item_x.title, their)
        self.assertIn(f'href="/listings/{self.item_x.id}"', their)
        self.assertIn(">IN_TRADE</span>", their)
        self.assertIn(f"Other party {self.user_a.display_name}", incoming)
        self.assertIn(f"Proposed by {self.user_a.display_name}", incoming)
        self.assertIn(
            'class="trade-status trade-status-proposed">PROPOSED</span>',
            incoming,
        )
        self.assertIn(f'action="/trades/{trade.id}/accept"', incoming)
        self.assertIn(">Accept</button>", incoming)
        self.assertIn(f'action="/trades/{trade.id}/reject"', incoming)
        self.assertIn(">Reject</button>", incoming)
        self.assertNotIn("/cancel", incoming)
        self.assertNotIn(">Cancel</button>", incoming)
        self.assertNotIn(self.item_x.title, outgoing)
        self.assertNotIn(self.item_y.title, outgoing)
        self.assertNotIn(self.item_x.title, finished)
        self.assertNotIn(self.item_y.title, finished)

    def test_outgoing_proposal_rendered_for_the_proposer(self):
        """Spec 06 case 28: the proposer sees the trade under Outgoing proposals."""
        trade = self._propose()

        html = self._page(self.user_a)

        incoming, outgoing, finished = _trade_sections(html)
        your, their = outgoing.split("Their item", 1)
        self.assertIn(self.item_x.title, your)
        self.assertIn(f'href="/listings/{self.item_x.id}"', your)
        self.assertIn(self.item_y.title, their)
        self.assertIn(f'href="/listings/{self.item_y.id}"', their)
        self.assertIn(f"Other party {self.user_b.display_name}", outgoing)
        self.assertIn("Proposed by You", outgoing)
        self.assertEqual(outgoing.count("<form"), 1)
        self.assertIn(f'action="/trades/{trade.id}/cancel"', outgoing)
        self.assertIn(">Cancel</button>", outgoing)
        self.assertNotIn("/accept", outgoing)
        self.assertNotIn("/reject", outgoing)
        self.assertNotIn(self.item_x.title, incoming)
        self.assertNotIn(self.item_y.title, incoming)
        self.assertNotIn(self.item_x.title, finished)
        self.assertNotIn(self.item_y.title, finished)

    def test_third_user_does_not_see_the_trade(self):
        """Spec 06 case 28: a third user sees the trade in none of the three sections."""
        trade = self._propose()

        html = self._page(self.user_c)

        self.assertNotIn(f"/trades/{trade.id}/", html)
        self.assertNotIn(self.item_x.title, html)
        self.assertNotIn(self.item_y.title, html)

    def _assert_finished(self, status_text, badge_text):
        css = status_text.lower()
        for user, your_item, their_item, proposed_by in (
            (self.user_a, self.item_x, self.item_y, "You"),
            (self.user_b, self.item_y, self.item_x, self.user_a.display_name),
        ):
            with self.subTest(user=user.display_name):
                html = self._page(user)
                incoming, outgoing, finished = _trade_sections(html)
                your, their = finished.split("Their item", 1)
                self.assertIn(your_item.title, your)
                self.assertIn(their_item.title, their)
                self.assertIn(f">{badge_text}</span>", your)
                self.assertIn(f">{badge_text}</span>", their)
                self.assertIn(
                    f'class="trade-status trade-status-{css}">{status_text}</span>',
                    finished,
                )
                self.assertIn(f"Proposed by {proposed_by}", finished)
                row = finished.split('<li class="trade-row">', 1)[1].split("</li>", 1)[0]
                self.assertNotIn("<form", row)
                self.assertNotIn(self.item_x.title, incoming)
                self.assertNotIn(self.item_y.title, incoming)
                self.assertNotIn(self.item_x.title, outgoing)
                self.assertNotIn(self.item_y.title, outgoing)

    def test_accepted_trade_renders_under_finished(self):
        """Spec 06 case 29: an accepted trade is listed under Finished trades."""
        trade = self._propose()
        accept_trade(self.user_b, trade)
        self._assert_finished("ACCEPTED", "TRADED")

    def test_rejected_trade_renders_under_finished(self):
        """Spec 06 case 29: a rejected trade is listed under Finished trades."""
        trade = self._propose()
        reject_trade(self.user_b, trade)
        self._assert_finished("REJECTED", "AVAILABLE")

    def test_cancelled_trade_renders_under_finished(self):
        """Spec 06 case 29: a cancelled trade is listed under Finished trades."""
        trade = self._propose()
        cancel_trade(self.user_a, trade)
        self._assert_finished("CANCELLED", "AVAILABLE")

    def test_demo_flow_propose_then_accept(self):
        """Spec 06 case 30: propose then accept moves both listings to TRADED."""
        match_items(self.item_x, self.item_y)
        match_id = _match_id(self.item_x, self.item_y)
        self.client.force_login(self.user_a)

        proposed = self.client.post(f"/matches/{match_id}/propose")

        self.assertEqual(proposed.status_code, 302)
        self.assertEqual(proposed["Location"], "/matches")
        browse = self.client.get("/").content.decode()
        self.assertIn(">IN_TRADE</span>", _listing_card(browse, self.item_x.title))
        self.assertIn(">IN_TRADE</span>", _listing_card(browse, self.item_y.title))

        trade = Trade.objects.get()
        self.client.force_login(self.user_b)
        accepted = self.client.post(f"/trades/{trade.id}/accept")

        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(accepted["Location"], "/matches")
        browse = self.client.get("/").content.decode()
        self.assertIn(">TRADED</span>", _listing_card(browse, self.item_x.title))
        self.assertIn(">TRADED</span>", _listing_card(browse, self.item_y.title))

        for user in (self.user_a, self.user_b):
            with self.subTest(user=user.display_name):
                html = self._page(user)
                _incoming, _outgoing, finished = _trade_sections(html)
                self.assertIn(
                    'class="trade-status trade-status-accepted">ACCEPTED</span>',
                    finished,
                )
                self.assertIn(self.item_x.title, finished)
                self.assertIn(self.item_y.title, finished)
