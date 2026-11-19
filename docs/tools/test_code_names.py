"""Checks which text in code font is taken for which C# name (tools/code_names.py).

Run with:  ./test.sh
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import code_names


def sample():
    names = code_names.CodeNames()
    names.add_namespace("Shop.Orders")
    for name in ("Shop.Orders.Order", "Shop.Orders.Result-1", "Shop.Orders.OrderState", "Shop.Orders.Setup",
                 "Shop.Billing.Setup", "Shop.Orders.Order.Line", "Program"):
        names.add_type(name)
    for name in ("Shop.Orders.Order.Close", "Shop.Orders.Order.Total", "Shop.Orders.Result-1.NotFound",
                 "Shop.Orders.OrderState.Closed", "Shop.Billing.Setup.Close"):
        names.add_member(name)
    return names


class Resolve(unittest.TestCase):
    def setUp(self):
        self.names = sample()

    def test_the_short_name_of_a_type(self):
        self.assertEqual(self.names.resolve("Order"), "Shop.Orders.Order")
        self.assertEqual(self.names.resolve("Program"), "Program")
        self.assertEqual(self.names.resolve(" Order? "), "Shop.Orders.Order")

    def test_a_generic_type_is_filed_with_the_number_of_its_type_parameters(self):
        self.assertEqual(self.names.resolve("Result<T>"), "Shop.Orders.Result-1")
        self.assertEqual(self.names.resolve("Result<List<Order>>"), "Shop.Orders.Result-1")
        self.assertEqual(self.names.resolve("Result"), "Shop.Orders.Result-1")

    def test_a_member_written_with_its_type(self):
        self.assertEqual(self.names.resolve("Order.Close()"), "Shop.Orders.Order.Close")
        self.assertEqual(self.names.resolve("Order.Close(reason, now)"), "Shop.Orders.Order.Close")
        self.assertEqual(self.names.resolve("Order.Total"), "Shop.Orders.Order.Total")
        self.assertEqual(self.names.resolve("OrderState.Closed"), "Shop.Orders.OrderState.Closed")
        self.assertEqual(self.names.resolve("Result<Order>.NotFound()"), "Shop.Orders.Result-1.NotFound")

    def test_a_type_inside_a_type(self):
        self.assertEqual(self.names.resolve("Line"), "Shop.Orders.Order.Line")
        self.assertEqual(self.names.resolve("Order.Line"), "Shop.Orders.Order.Line")

    def test_full_names(self):
        self.assertEqual(self.names.resolve("Shop.Orders"), "Shop.Orders")
        self.assertEqual(self.names.resolve("Shop.Orders.Order"), "Shop.Orders.Order")
        self.assertEqual(self.names.resolve("Shop.Orders.Result<T>"), "Shop.Orders.Result-1")
        self.assertEqual(self.names.resolve("Shop.Billing.Setup"), "Shop.Billing.Setup")
        self.assertEqual(self.names.resolve("Shop.Orders.Order.Close()"), "Shop.Orders.Order.Close")

    def test_a_short_name_that_two_types_share_is_not_guessed(self):
        self.assertIsNone(self.names.resolve("Setup"))

    def test_a_member_on_its_own_is_not_understood(self):
        for text in ("Close", "Close()", "Total", "NotFound", "Closed"):
            with self.subTest(text=text):
                self.assertIsNone(self.names.resolve(text))

    def test_text_that_is_not_a_name(self):
        for text in ("", "order", "Order.cs", "Order.Missing", "var order = new Order()", "new Order()", "--no-build",
                     "Orders.Order.Close", "GET /orders/{id}", "Order, Result", "Order[]", "Shop", "Shop.Orders.Nothing"):
            with self.subTest(text=text):
                self.assertIsNone(self.names.resolve(text))

    def test_owner(self):
        self.assertEqual(self.names.owner("Shop.Orders.Order.Close"), "Shop.Orders.Order")
        self.assertEqual(self.names.owner("Shop.Orders.Result-1.NotFound"), "Shop.Orders.Result-1")
        self.assertEqual(self.names.owner("Shop.Orders.Order"), "Shop.Orders.Order")
        self.assertIsNone(self.names.owner("Shop.Orders"))


INDEX = """<?xml version='1.0' encoding='UTF-8' standalone='no'?>
<doxygenindex>
  <compound refid="classShop_1_1Orders_1_1Order" kind="class"><name>Shop::Orders::Order</name>
    <member refid="classShop_1_1Orders_1_1Order_1a1" kind="function"><name>Order</name></member>
    <member refid="classShop_1_1Orders_1_1Order_1a2" kind="function"><name>Close</name></member>
    <member refid="classShop_1_1Orders_1_1Order_1a3" kind="function"><name>Map&lt; T &gt;</name></member>
    <member refid="classShop_1_1Orders_1_1Order_1a4" kind="property"><name>Total</name></member>
  </compound>
  <compound refid="classShop_1_1Orders_1_1Result-1-g" kind="class"><name>Shop::Orders::Result-1-g</name>
    <member refid="classShop_1_1Orders_1_1Result-1-g_1a1" kind="function"><name>NotFound</name></member>
  </compound>
  <compound refid="interfaceShop_1_1Orders_1_1IClock" kind="interface"><name>Shop::Orders::IClock</name>
    <member refid="interfaceShop_1_1Orders_1_1IClock_1a1" kind="property"><name>Now</name></member>
  </compound>
  <compound refid="classProgram" kind="class"><name>Program</name></compound>
  <compound refid="namespaceShop" kind="namespace"><name>Shop</name></compound>
  <compound refid="namespaceShop_1_1Orders" kind="namespace"><name>Shop::Orders</name>
    <member refid="namespaceShop_1_1Orders_1aaa" kind="enum"><name>OrderState</name></member>
    <member refid="namespaceShop_1_1Orders_1aaaa111" kind="enumvalue"><name>Open</name></member>
    <member refid="namespaceShop_1_1Orders_1aaaa222" kind="enumvalue"><name>Closed</name></member>
    <member refid="namespaceShop_1_1Orders_1abb" kind="enum"><name>Colour</name></member>
    <member refid="namespaceShop_1_1Orders_1abba333" kind="enumvalue"><name>Closed</name></member>
    <member refid="namespaceShop_1_1Orders_1acc" kind="function"><name>OrderView</name></member>
  </compound>
  <compound refid="Order_8cs" kind="file"><name>Order.cs</name></compound>
</doxygenindex>
"""


class FromDoxygen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory(prefix="stargate-docs-test-") as work:
            (Path(work) / "index.xml").write_text(INDEX, encoding="utf-8")
            cls.names = code_names.from_doxygen(work)

    def test_types(self):
        self.assertEqual(self.names.types, {
            "Shop.Orders.Order", "Shop.Orders.Result-1", "Shop.Orders.IClock", "Program",
            "Shop.Orders.OrderState", "Shop.Orders.Colour",
            "Shop.Orders.OrderView",      # a record written on one line: Doxygen calls it a function of the namespace
        })

    def test_members_and_their_types(self):
        self.assertEqual(self.names.resolve("Order.Close()"), "Shop.Orders.Order.Close")
        self.assertEqual(self.names.resolve("Order.Map<T>()"), "Shop.Orders.Order.Map")
        self.assertEqual(self.names.resolve("IClock.Now"), "Shop.Orders.IClock.Now")
        self.assertEqual(self.names.resolve("Result<Order>.NotFound()"), "Shop.Orders.Result-1.NotFound")
        self.assertEqual(self.names.owner("Shop.Orders.Result-1.NotFound"), "Shop.Orders.Result-1")

    def test_an_enum_value_belongs_to_the_enum_it_is_listed_under(self):
        self.assertEqual(self.names.resolve("OrderState.Closed"), "Shop.Orders.OrderState.Closed")
        self.assertEqual(self.names.resolve("Colour.Closed"), "Shop.Orders.Colour.Closed")
        self.assertIsNone(self.names.resolve("Colour.Open"))

    def test_a_constructor_does_not_hide_its_type(self):
        self.assertEqual(self.names.resolve("Order"), "Shop.Orders.Order")
        self.assertEqual(self.names.resolve("Shop.Orders.Order"), "Shop.Orders.Order")

    def test_namespaces(self):
        self.assertEqual(self.names.resolve("Shop.Orders"), "Shop.Orders")

    def test_no_xml_gives_no_names(self):
        with tempfile.TemporaryDirectory(prefix="stargate-docs-test-") as work:
            self.assertEqual(code_names.from_doxygen(work).types, set())


class FromInventory(unittest.TestCase):
    def setUp(self):
        def item(uri):
            return SimpleNamespace(uri=uri)
        inventory = {
            "cs:namespace": {"Shop.Orders": item("api/Shop.Orders.html#namespace-Shop.Orders")},
            "cs:class": {"Shop.Orders.Order": item("api/Shop.Orders.html#class-Shop.Orders.Order")},
            "cs:record": {"Shop.Orders.Result-1": item("api/Shop.Orders.html#record-Shop.Orders.Result-1")},
            "cs:enum": {"Shop.Orders.OrderState": item("api/Shop.Orders.html#enum-Shop.Orders.OrderState")},
            "cs:enumerator": {"Shop.Orders.OrderState.Closed": item("api/Shop.Orders.html#enumerator-Closed")},
            "cs:function": {
                "Shop.Orders.Order.Close": item("api/Shop.Orders.html#function-Close"),
                "Shop.Orders.Order.Close(string)": item("api/Shop.Orders.html#function-Close-string"),
                # A generic method is only filed with its brackets.
                "Shop.Orders.Order.Map<T>(Func<Order,T>)": item("api/Shop.Orders.html#function-Map"),
            },
            "cs:property": {"Shop.Orders.Order.Total": item("api/Shop.Orders.html#property-Total")},
            "std:doc": {"guide/patterns": item("guide/patterns.html")},
        }
        self.names, self.addresses = code_names.from_inventory(inventory)

    def test_every_name_has_its_address(self):
        expected = {
            "Order": "api/Shop.Orders.html#class-Shop.Orders.Order",
            "Result<T>": "api/Shop.Orders.html#record-Shop.Orders.Result-1",
            "OrderState.Closed": "api/Shop.Orders.html#enumerator-Closed",
            "Order.Close()": "api/Shop.Orders.html#function-Close",
            "Order.Map<T>()": "api/Shop.Orders.html#function-Map",
            "Order.Total": "api/Shop.Orders.html#property-Total",
            "Shop.Orders": "api/Shop.Orders.html#namespace-Shop.Orders",
        }
        for text, address in expected.items():
            with self.subTest(text=text):
                self.assertEqual(self.addresses[self.names.resolve(text)], address)

    def test_pages_are_not_names(self):
        self.assertIsNone(self.names.resolve("guide/patterns"))
        self.assertNotIn("guide/patterns", self.addresses)


if __name__ == "__main__":
    unittest.main()
