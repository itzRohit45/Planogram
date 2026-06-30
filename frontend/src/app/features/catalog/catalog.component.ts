import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpClientModule } from '@angular/common/http';

interface Product {
  id: number;
  name: string;
  image_path: string;
}

@Component({
  selector: 'app-catalog',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './catalog.component.html',
  styleUrl: './catalog.component.scss'
})
export class CatalogComponent implements OnInit {
  products: Product[] = [];
  productName: string = '';
  selectedFile: File | null = null;
  isLoading: boolean = false;
  message: string = '';

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.loadProducts();
  }

  loadProducts() {
    this.http.get<Product[]>('http://localhost:3000/api/products').subscribe({
      next: (data) => this.products = data,
      error: (err) => console.error(err)
    });
  }

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0];
  }

  uploadProduct() {
    if (!this.productName || !this.selectedFile) {
      this.message = 'Please provide a name and an image.';
      return;
    }

    this.isLoading = true;
    this.message = 'Extracting DINOv2 fingerprint... This may take a moment.';
    
    const formData = new FormData();
    formData.append('name', this.productName);
    formData.append('image', this.selectedFile);

    this.http.post('http://localhost:3000/api/products', formData).subscribe({
      next: () => {
        this.isLoading = false;
        this.message = 'Product added successfully!';
        this.productName = '';
        this.selectedFile = null;
        this.loadProducts();
      },
      error: (err) => {
        this.isLoading = false;
        this.message = 'Error: ' + (err.error?.error || 'Failed to add product');
      }
    });
  }

  deleteProduct(id: number) {
    if(confirm('Are you sure you want to delete this product?')) {
      this.http.delete(`http://localhost:3000/api/products/${id}`).subscribe({
        next: () => this.loadProducts(),
        error: (err) => console.error(err)
      });
    }
  }

  getImageUrl(path: string): string {
    const filename = path.split('/').pop() || path.split('\\').pop();
    return `http://localhost:3000/uploads/catalog/${filename}`;
  }
}
