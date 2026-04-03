const product = {
  name: "Laptop",
  brand: "Dell",
  price: 75000,
  category: "Electronics",
  stock: 10,

  displayDetails: function () {
    console.log("Product:", this.name);
    console.log("Brand:", this.brand);
    console.log("Price:", this.price);
  },

  checkStock: function () {
    console.log("Available Stock:", this.stock);
  }
};

product.displayDetails();
product.checkStock();