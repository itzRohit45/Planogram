import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterOutlet } from '@angular/router';
import { ApiService, BaselineResponse, AuditResponse } from './services/api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterOutlet],
  templateUrl: './app.component.html',
  styleUrls: ['../styles.scss', './app.component.scss']
})
export class AppComponent implements OnInit {
  title = 'Shelf Compliance Auditing';
  
  view: 'dashboard' | 'baseline' | 'audit' | 'report' | 'baseline_view' = 'dashboard';
  
  // Dashboard state
  baselines: any[] = [];
  audits: any[] = [];
  
  // Upload state
  selectedFile: File | null = null;
  selectedBaselineId: number | null = null;
  uploadName: string = '';
  isUploading = false;
  uploadError = '';
  
  // Report state
  currentReport: AuditResponse | null = null;
  currentBaseline: any = null;
  
  // Dashboard computed stats
  get totalBaselines() { return this.baselines.length; }
  get totalAudits() { return this.audits.length; }
  get averageCompliance() {
    if (this.audits.length === 0) return 0;
    const total = this.audits.reduce((sum, a) => sum + (a.compliance_score || 0), 0);
    return Math.round(total / this.audits.length);
  }
  
  constructor(public api: ApiService) {}

  ngOnInit() {
    this.loadDashboard();
  }

  loadDashboard() {
    this.view = 'dashboard';
    this.currentBaseline = null;
    this.api.getBaselines().subscribe({
      next: (data) => this.baselines = data,
      error: (err) => console.error(err)
    });
    this.api.getAudits().subscribe({
      next: (data) => this.audits = data,
      error: (err) => console.error(err)
    });
  }

  deleteBaseline(event: Event, id: number) {
    event.stopPropagation();
    if (confirm('Are you sure you want to delete this baseline?')) {
      this.api.deleteBaseline(id).subscribe(() => this.loadDashboard());
    }
  }

  deleteAudit(event: Event, id: number) {
    event.stopPropagation();
    if (confirm('Are you sure you want to delete this audit?')) {
      this.api.deleteAudit(id).subscribe(() => this.loadDashboard());
    }
  }

  viewBaseline(baseline: any) {
    this.currentBaseline = baseline;
    this.view = 'baseline_view';
  }

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
        this.loadDashboard();
      },
      error: (err) => {
        this.isUploading = false;
        this.uploadError = err.error?.error || 'Failed to upload baseline';
      }
    });
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
        this.currentReport = res;
        this.view = 'report';
      },
      error: (err) => {
        this.isUploading = false;
        this.uploadError = err.error?.error || 'Failed to upload audit';
      }
    });
  }

  viewReport(audit: any) {
    // In a real app we'd fetch full report json from URL. 
    // For simplicity, we just use the data if available or fetch it
    fetch(`${this.api.baseUrl}/reports/${audit.report_path}`)
      .then(res => res.json())
      .then(data => {
        this.currentReport = {
          id: audit.id,
          compliance_score: audit.compliance_score,
          fill_rate: audit.fill_rate,
          report_path: audit.report_path,
          visual_report_path: audit.visual_report_path,
          comparison_report: data,
          message: ''
        };
        this.view = 'report';
      })
      .catch(err => console.error('Failed to load report data', err));
  }

  getBoxStyle(box: any, imgWidth: number, imgHeight: number) {
    if (!box) return {};
    const left = (box.x1 / imgWidth) * 100;
    const top = (box.y1 / imgHeight) * 100;
    const width = ((box.x2 - box.x1) / imgWidth) * 100;
    const height = ((box.y2 - box.y1) / imgHeight) * 100;
    return {
      left: `${left}%`,
      top: `${top}%`,
      width: `${width}%`,
      height: `${height}%`
    };
  }

  hoveredBoxInfo: string | null = null;

  showBoxInfo(info: string) {
    this.hoveredBoxInfo = info;
  }

  hideBoxInfo() {
    this.hoveredBoxInfo = null;
  }
}
