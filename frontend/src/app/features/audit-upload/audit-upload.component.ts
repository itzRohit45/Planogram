import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { SharedDataService } from '../../services/shared-data.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-audit-upload',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './audit-upload.component.html',
  styleUrls: ['./audit-upload.component.scss']
})
export class AuditUploadComponent implements OnInit {
  baselines: any[] = [];
  selectedFile: File | null = null;
  selectedBaselineId: number | null = null;
  uploadName: string = '';
  isUploading = false;
  uploadError = '';

  constructor(
    public api: ApiService, 
    private shared: SharedDataService,
    private router: Router
  ) {}

  ngOnInit() {
    this.api.getBaselines().subscribe({
      next: (data) => this.baselines = data,
      error: (err) => console.error(err)
    });
  }

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0];
  }

  uploadAudit() {
    if (!this.selectedFile || !this.selectedBaselineId) return;
    this.isUploading = true;
    this.uploadError = '';
    
    this.api.uploadAudit(this.selectedFile, this.selectedBaselineId, this.uploadName).subscribe({
      next: (res) => {
        this.isUploading = false;
        this.selectedFile = null;
        this.uploadName = '';
        this.shared.currentReport = res;
        this.router.navigate(['/report']);
      },
      error: (err) => {
        this.isUploading = false;
        this.uploadError = err.error?.error || 'Failed to upload audit';
      }
    });
  }
}
