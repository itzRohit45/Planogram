import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, AuditResponse } from '../../services/api.service';
import { SharedDataService } from '../../services/shared-data.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-compliance-report',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './compliance-report.component.html',
  styleUrls: ['./compliance-report.component.scss']
})
export class ComplianceReportComponent implements OnInit {
  currentReport: AuditResponse | null = null;
  hoveredBoxInfo: { type: string, text: string } | null = null;
  expandedRow: number | null = null;
  objectKeys = Object.keys; // for template iteration

  constructor(
    public api: ApiService,
    private shared: SharedDataService,
    private router: Router
  ) {}

  toggleRow(rowNum: number) {
    this.expandedRow = this.expandedRow === rowNum ? null : rowNum;
  }

  ngOnInit() {
    this.currentReport = this.shared.currentReport;
    if (!this.currentReport) {
      this.router.navigate(['/dashboard']);
    }
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

  showBoxInfo(type: string, text: string) {
    this.hoveredBoxInfo = { type, text };
  }

  hideBoxInfo() {
    this.hoveredBoxInfo = null;
  }
}
