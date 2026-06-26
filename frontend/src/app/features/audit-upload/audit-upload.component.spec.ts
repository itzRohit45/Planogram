import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AuditUploadComponent } from './audit-upload.component';

describe('AuditUploadComponent', () => {
  let component: AuditUploadComponent;
  let fixture: ComponentFixture<AuditUploadComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AuditUploadComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AuditUploadComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
