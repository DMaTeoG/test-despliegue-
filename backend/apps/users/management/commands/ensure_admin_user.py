from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Crea o actualiza el usuario admin para pruebas'

    def handle(self, *args, **options):
        User = get_user_model()
        from apps.users.models import Role
        try:
            role = Role.objects.get(name='Administrador Sistema')
        except Role.DoesNotExist:
            role = None

        username = 'admin'
        password = 'admin123'
        email = 'admin@example.com'
        user, created = User.objects.get_or_create(username=username, defaults={
            'email': email,
            'is_active': True,
            'is_staff': True,
            'is_superuser': True,
            'role': role,
        })
        if not created:
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.email = email
            if role:
                user.role = role
            user.set_password(password)
            user.save()
        else:
            user.set_password(password)
            user.save()
        self.stdout.write(self.style.SUCCESS(f"Usuario admin {'creado' if created else 'actualizado'} y activo con rol Administrador Sistema."))
