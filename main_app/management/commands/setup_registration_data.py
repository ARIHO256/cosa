from django.core.management.base import BaseCommand
from main_app.models import Department, Degree, GraduationYear, Company


class Command(BaseCommand):
    help = 'Setup initial data required for alumni registration'

    def handle(self, *args, **options):
        self.stdout.write('Setting up registration data...')
        
        # Create departments
        departments_data = [
            {'name': 'Computer Science', 'code': 'CS', 'description': 'Computer Science Department'},
            {'name': 'Information Technology', 'code': 'IT', 'description': 'Information Technology Department'},
            {'name': 'Business Administration', 'code': 'BA', 'description': 'Business Administration Department'},
            {'name': 'Engineering', 'code': 'ENG', 'description': 'Engineering Department'},
            {'name': 'Arts and Sciences', 'code': 'AS', 'description': 'Arts and Sciences Department'},
        ]
        
        for dept_data in departments_data:
            dept, created = Department.objects.get_or_create(
                code=dept_data['code'],
                defaults=dept_data
            )
            if created:
                self.stdout.write(f'Created department: {dept.name}')
            else:
                self.stdout.write(f'Department already exists: {dept.name}')
        
        # Create degrees
        degrees_data = [
            {'name': 'Bachelor of Computer Science', 'degree_type': 'Bachelor', 'department': 'CS', 'duration_years': 4},
            {'name': 'Bachelor of Information Technology', 'degree_type': 'Bachelor', 'department': 'IT', 'duration_years': 4},
            {'name': 'Bachelor of Business Administration', 'degree_type': 'Bachelor', 'department': 'BA', 'duration_years': 4},
            {'name': 'Bachelor of Engineering', 'degree_type': 'Bachelor', 'department': 'ENG', 'duration_years': 4},
            {'name': 'Master of Computer Science', 'degree_type': 'Master', 'department': 'CS', 'duration_years': 2},
            {'name': 'Master of Business Administration', 'degree_type': 'Master', 'department': 'BA', 'duration_years': 2},
            {'name': 'PhD in Computer Science', 'degree_type': 'PhD', 'department': 'CS', 'duration_years': 3},
        ]
        
        for degree_data in degrees_data:
            dept = Department.objects.get(code=degree_data['department'])
            degree, created = Degree.objects.get_or_create(
                name=degree_data['name'],
                defaults={
                    'degree_type': degree_data['degree_type'],
                    'department': dept,
                    'duration_years': degree_data['duration_years'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'Created degree: {degree.name}')
            else:
                self.stdout.write(f'Degree already exists: {degree.name}')
        
        # Create graduation years (last 20 years)
        from datetime import datetime
        current_year = datetime.now().year
        for year in range(current_year - 20, current_year + 5):
            grad_year, created = GraduationYear.objects.get_or_create(
                year=year,
                defaults={'is_active': True}
            )
            if created:
                self.stdout.write(f'Created graduation year: {year}')
        
        # Create sample companies
        companies_data = [
            {'name': 'Apple Inc.', 'industry': 'Technology', 'website': 'https://apple.com', 'description': 'Technology company'},
            {'name': 'Google LLC', 'industry': 'Technology', 'website': 'https://google.com', 'description': 'Search and technology company'},
            {'name': 'Microsoft Corporation', 'industry': 'Technology', 'website': 'https://microsoft.com', 'description': 'Software and technology company'},
            {'name': 'Amazon.com Inc.', 'industry': 'E-commerce', 'website': 'https://amazon.com', 'description': 'E-commerce and cloud computing'},
            {'name': 'Facebook Inc.', 'industry': 'Social Media', 'website': 'https://facebook.com', 'description': 'Social media platform'},
            {'name': 'Netflix Inc.', 'industry': 'Entertainment', 'website': 'https://netflix.com', 'description': 'Streaming entertainment service'},
        ]
        
        for company_data in companies_data:
            company, created = Company.objects.get_or_create(
                name=company_data['name'],
                defaults={
                    'industry': company_data['industry'],
                    'website': company_data['website'],
                    'description': company_data['description'],
                    'is_verified': True,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'Created company: {company.name}')
            else:
                self.stdout.write(f'Company already exists: {company.name}')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully setup registration data!')
        )

