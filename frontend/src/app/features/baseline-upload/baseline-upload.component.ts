import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-baseline-upload',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './baseline-upload.component.html',
  styleUrls: ['./baseline-upload.component.scss']
})
export class BaselineUploadComponent {
  selectedFile: File | null = null;
  uploadName: string = '';
  isUploading = false;
  uploadError = '';

  constructor(public api: ApiService, private router: Router) {}

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0];
  }

  uploadBaseline() {
    if (!this.selectedFile) return;
    this.isUploading = true;
    this.uploadError = '';
    
    this.api.uploadBaseline(this.selectedFile, this.uploadName).subscribe({
      next: (res) => {
        this.isUploading = false;
        this.selectedFile = null;
        this.uploadName = '';
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.isUploading = false;
        this.uploadError = err.error?.error || 'Failed to upload baseline';
      }
    });
  }
}
