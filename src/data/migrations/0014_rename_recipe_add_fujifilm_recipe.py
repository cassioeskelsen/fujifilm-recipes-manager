from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0013_add_d_range_priority_to_fujifilmrecipe'),
    ]

    operations = [
        # Rename Image.recipe -> Image.fujifilm_exif
        migrations.RenameField(
            model_name='image',
            old_name='recipe',
            new_name='fujifilm_exif',
        ),
        # Add Image.fujifilm_recipe (nullable FK to FujifilmRecipe)
        migrations.AddField(
            model_name='image',
            name='fujifilm_recipe',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='images',
                to='data.fujifilmrecipe',
            ),
        ),
        # Make FujifilmRecipe numeric fields nullable
        migrations.AlterField(
            model_name='fujifilmrecipe',
            name='highlight',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='fujifilmrecipe',
            name='shadow',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='fujifilmrecipe',
            name='color',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='fujifilmrecipe',
            name='sharpness',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='fujifilmrecipe',
            name='high_iso_nr',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='fujifilmrecipe',
            name='clarity',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='fujifilmrecipe',
            name='monochromatic_color_warm_cool',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='fujifilmrecipe',
            name='monochromatic_color_magenta_green',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
