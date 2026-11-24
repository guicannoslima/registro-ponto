from django.db import migrations

FUNCOES = ('Auxiliar de Suporte', 'Programador Júnior', 'Supervisora Financeira', 'Coordenadora de Processos')


def carregar(apps, schema_editor):
    Funcao = apps.get_model('ponto', 'Funcao')
    for nome in FUNCOES:
        Funcao.objects.using(schema_editor.connection.alias).get_or_create(nome=nome)


class Migration(migrations.Migration):
    dependencies = [('ponto', '0013_folga')]
    operations = [migrations.RunPython(carregar, migrations.RunPython.noop)]
