from django.db import migrations


def carregar(apps, schema_editor):
    Jornada = apps.get_model('ponto', 'Jornada')
    modelos = [
        ('40h · Seg–sex · 08h', ['08:00', '12:00', '13:00', '', '', '17:00'], 5, None),
        ('40h · Seg–sex · 09h', ['09:00', '12:00', '13:00', '', '', '18:00'], 5, None),
        ('44h · Seg–sáb · 08h', ['08:00', '12:00', '13:00', '', '', '17:00'], 5, ['08:00', '', '', '', '', '12:00']),
        ('44h · Compensação sábado · 08h', ['08:00', '12:00', '13:00', '', '', '17:48'], 5, None),
        ('36h · Seg–sáb · 08h', ['08:00', '11:00', '11:15', '', '', '14:15'], 6, None),
        ('30h · Seg–sex · 08h', ['08:00', '11:00', '11:15', '', '', '14:15'], 5, None),
        ('26h · Seg–sex · 08h', ['08:00', '11:00', '11:15', '', '', '13:27'], 5, None),
        ('20h · Seg–sex · 08h', ['08:00', '', '', '', '', '12:00'], 5, None),
    ]
    for nome, horas, dias, sabado in modelos:
        semana = {str(dia): horas for dia in range(dias)}
        if sabado:
            semana['5'] = sabado
        Jornada.objects.using(schema_editor.connection.alias).get_or_create(nome=nome, defaults={'semana': semana})


class Migration(migrations.Migration):
    dependencies = [('ponto', '0011_feriado_jornada_vinculojornada')]
    operations = [migrations.RunPython(carregar, migrations.RunPython.noop)]
