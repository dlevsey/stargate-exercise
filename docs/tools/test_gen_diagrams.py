"""Checks the data model page and the projects page (tools/gen_diagrams.py).

Run with:  ./test.sh
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gen_diagrams
from gen_diagrams import model_graph, on_delete, read_project, read_snapshot

# The format Entity Framework Core writes a model snapshot in.
SNAPSHOT = """
namespace Shop.Migrations
{
    [DbContext(typeof(ShopContext))]
    partial class ShopContextModelSnapshot : ModelSnapshot
    {
        protected override void BuildModel(ModelBuilder modelBuilder)
        {
#pragma warning disable 612, 618
            modelBuilder.HasAnnotation("ProductVersion", "8.0.4");

            modelBuilder.Entity("Shop.Data.Customer", b =>
                {
                    b.Property<int>("Id")
                        .ValueGeneratedOnAdd()
                        .HasColumnType("INTEGER");

                    b.Property<string>("Name")
                        .IsRequired()
                        .HasMaxLength(200)
                        .HasColumnType("TEXT");

                    b.Property<string>("Nickname")
                        .HasColumnType("TEXT");

                    b.HasKey("Id");

                    b.HasIndex("Name")
                        .IsUnique();

                    b.ToTable("Customers");
                });

            modelBuilder.Entity("Shop.Data.Order", b =>
                {
                    b.Property<int>("Id")
                        .ValueGeneratedOnAdd()
                        .HasColumnType("INTEGER");

                    b.Property<int>("CustomerId")
                        .HasColumnType("INTEGER");

                    b.Property<DateTime?>("PaidOn")
                        .HasColumnType("TEXT");

                    b.HasKey("Id");

                    b.HasIndex("CustomerId");

                    b.ToTable("Order");
                });

            modelBuilder.Entity("Shop.Data.Profile", b =>
                {
                    b.Property<int>("Id")
                        .HasColumnType("INTEGER");

                    b.Property<int>("CustomerId")
                        .HasColumnType("INTEGER");

                    b.HasKey("Id");

                    b.HasIndex("CustomerId")
                        .IsUnique();

                    b.ToTable("Profile");
                });

            modelBuilder.Entity("Shop.Data.Order", b =>
                {
                    b.HasOne("Shop.Data.Customer", "Customer")
                        .WithMany("Orders")
                        .HasForeignKey("CustomerId")
                        .OnDelete(DeleteBehavior.Restrict);

                    b.Navigation("Customer");
                });

            modelBuilder.Entity("Shop.Data.Profile", b =>
                {
                    b.HasOne("Shop.Data.Customer", "Customer")
                        .WithOne("Profile")
                        .HasForeignKey("Shop.Data.Profile", "CustomerId")
                        .OnDelete(DeleteBehavior.Cascade)
                        .IsRequired();

                    b.Navigation("Customer");
                });

            modelBuilder.Entity("Shop.Data.Customer", b =>
                {
                    b.Navigation("Orders");

                    b.Navigation("Profile");
                });
#pragma warning restore 612, 618
        }
    }
}
"""


class Snapshot(unittest.TestCase):
    def setUp(self):
        self.entities, self.relationships = read_snapshot(SNAPSHOT)

    def test_the_tables_and_their_names(self):
        self.assertEqual({name: entity["table"] for name, entity in self.entities.items()},
                         {"Shop.Data.Customer": "Customers", "Shop.Data.Order": "Order", "Shop.Data.Profile": "Profile"})

    def test_the_columns_of_a_table(self):
        columns = {column["name"]: column for column in self.entities["Shop.Data.Customer"]["columns"]}
        self.assertEqual(list(columns), ["Id", "Name", "Nickname"])
        self.assertEqual(columns["Id"], {"name": "Id", "type": "int", "column_type": "INTEGER", "required": True, "generated": True})
        self.assertTrue(columns["Name"]["required"])            # IsRequired()
        self.assertFalse(columns["Nickname"]["required"])       # a string without IsRequired() may be empty
        paid_on = self.entities["Shop.Data.Order"]["columns"][2]
        self.assertEqual((paid_on["type"], paid_on["required"]), ("DateTime?", False))

    def test_keys_and_indexes(self):
        customer = self.entities["Shop.Data.Customer"]
        self.assertEqual(customer["key"], ["Id"])
        self.assertEqual(customer["indexes"], [{"columns": ["Name"], "unique": True}])
        self.assertEqual(self.entities["Shop.Data.Order"]["indexes"], [{"columns": ["CustomerId"], "unique": False}])

    def test_relationships(self):
        self.assertEqual(self.relationships, [
            {"child": "Shop.Data.Order", "parent": "Shop.Data.Customer", "columns": ["CustomerId"], "to_one": False,
             "on_delete": "Restrict", "required": False},
            {"child": "Shop.Data.Profile", "parent": "Shop.Data.Customer", "columns": ["CustomerId"], "to_one": True,
             "on_delete": "Cascade", "required": True},
        ])

    def test_the_drawing(self):
        linked = {"Shop.Data.Customer": "class-Shop.Data.Customer"}
        graph = model_graph(self.entities, self.relationships, linked)
        self.assertIn('URL="../api/Shop.Data.html#class-Shop.Data.Customer"', graph)     # a class with an entry
        self.assertEqual(graph.count("URL="), 1)                                           # and only that one
        # A line leaves on the right of the row that holds the column and arrives on the left of the key's row.
        self.assertIn('"Shop.Data.Order":"CustomerId.out":e -> "Shop.Data.Customer":"Id":w [arrowtail=crow];', graph)
        self.assertIn('"Shop.Data.Profile":"CustomerId.out":e -> "Shop.Data.Customer":"Id":w [arrowtail=tee];', graph)
        self.assertIn('PORT="CustomerId.out"', graph)
        self.assertIn(">PK </FONT>", graph)          # Customer.Id
        self.assertIn(">FK UQ </FONT>", graph)       # Profile.CustomerId: points at a customer, one profile each

    def test_what_happens_on_delete_in_plain_words(self):
        self.assertEqual(on_delete("Cascade"), "the rows that point at it are deleted too (`Cascade`)")
        self.assertEqual(on_delete("SomethingNew"), "`SomethingNew`")
        self.assertEqual(on_delete(""), "not said")


class Project(unittest.TestCase):
    def test_what_a_project_file_says(self):
        with tempfile.TemporaryDirectory(prefix="stargate-docs-test-") as folder:
            repo = Path(folder)
            project_file = repo / "src" / "Shop.Api" / "Shop.Api.csproj"
            project_file.parent.mkdir(parents=True)
            project_file.write_text("""<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Swashbuckle.AspNetCore" Version="6.5.0" />
    <PackageReference Include="Dapper" Version="2.1.35" />
    <PackageReference Include="Tools.Package"><Version>1.0.0</Version><PrivateAssets>all</PrivateAssets></PackageReference>
    <PackageReference Include="Centrally.Versioned" />
  </ItemGroup>
  <ItemGroup><ProjectReference Include="..\\Shop.Domain\\Shop.Domain.csproj" /></ItemGroup>
</Project>""", encoding="utf-8")
            with mock.patch.object(gen_diagrams, "REPO", repo):
                project = read_project(project_file)
        self.assertEqual(project, {
            "name": "Shop.Api", "path": "src/Shop.Api/Shop.Api.csproj", "sdk": "Microsoft.NET.Sdk.Web", "framework": "net8.0",
            "packages": [("Centrally.Versioned", ""), ("Dapper", "2.1.35"), ("Swashbuckle.AspNetCore", "6.5.0"),
                         ("Tools.Package", "1.0.0")],
            "uses": ["Shop.Domain"], "tests": False,
        })


if __name__ == "__main__":
    unittest.main()
