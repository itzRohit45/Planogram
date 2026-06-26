import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';
import { SharedDataService } from '../../services/shared-data.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {
  baselines: any[] = [];
  audits: any[] = [];

  get totalBaselines() { return this.baselines.length; }
  get totalAudits() { return this.audits.length; }
  get averageCompliance() {
    if (this.audits.length === 0) return 0;
    const total = this.audits.reduce((sum, a) => sum + (a.compliance_score || 0), 0);
    return Math.round(total / this.audits.length);
  }

  constructor(public api: ApiService, private shared: SharedDataService, private router: Router) {}

  ngOnInit() {
    this.loadDashboard();
  }

  loadDashboard() {
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
    // Currently no standalone route for baseline view in the router config,
    // but we can route to baseline or just show a modal. We will route to baseline upload for now.
    // Ideally we would have a dedicated view.
  }

  viewReport(audit: any) {
    fetch(`${this.api.baseUrl}/reports/${audit.report_path}`)
      .then(res => res.json())
      .then(data => {
        this.shared.currentReport = {
          id: audit.id,
          compliance_score: audit.compliance_score,
          fill_rate: audit.fill_rate,
          report_path: audit.report_path,
          visual_report_path: audit.visual_report_path,
          comparison_report: data,
          message: ''
        };
        this.router.navigate(['/report']);
      })
      .catch(err => console.error('Failed to load report data', err));
  }
}
