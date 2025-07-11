import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import json
import asyncio
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional

class ProjectData:
    """Handles project data persistence"""
    def __init__(self, filename="projects.json"):
        self.filename = filename
        self.projects = self.load_projects()
    
    def load_projects(self) -> Dict:
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_projects(self):
        with open(self.filename, 'w') as f:
            json.dump(self.projects, f, indent=2)
    
    def create_project(self, project_id: str, project_data: Dict):
        self.projects[project_id] = project_data
        self.save_projects()
    
    def update_project(self, project_id: str, updates: Dict):
        if project_id in self.projects:
            self.projects[project_id].update(updates)
            self.save_projects()
    
    def delete_project(self, project_id: str):
        if project_id in self.projects:
            del self.projects[project_id]
            self.save_projects()
    
    def get_project(self, project_id: str) -> Optional[Dict]:
        return self.projects.get(project_id)
    
    def get_all_projects(self) -> Dict:
        return self.projects

class CreateProjectModal(Modal, title="Create New Project"):
    def __init__(self, project_data: ProjectData):
        super().__init__()
        self.project_data = project_data
    
    name = TextInput(
        label="Project Name",
        placeholder="Enter project name (e.g., Castle Tower)",
        max_length=50,
        required=True
    )
    
    description = TextInput(
        label="Description",
        placeholder="Brief description of the project",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )
    
    dimensions = TextInput(
        label="Dimensions",
        placeholder="e.g., 50x50x100 or Large castle",
        max_length=100,
        required=False
    )
    
    coordinates = TextInput(
        label="Coordinates (Optional)",
        placeholder="e.g., X: 100, Y: 64, Z: -200",
        max_length=100,
        required=False
    )
    
    estimated_time = TextInput(
        label="Estimated Completion Time",
        placeholder="e.g., 2 weeks, 5 days, 1 month",
        max_length=50,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        project_id = f"proj_{len(self.project_data.projects) + 1:03d}"
        
        project_info = {
            "id": project_id,
            "name": str(self.name),
            "description": str(self.description),
            "dimensions": str(self.dimensions) if self.dimensions else "Not specified",
            "coordinates": str(self.coordinates) if self.coordinates else "Not specified",
            "estimated_time": str(self.estimated_time) if self.estimated_time else "Not specified",
            "creator": interaction.user.display_name,
            "creator_id": interaction.user.id,
            "collaborators": [],
            "materials": [],
            "status": "Planning",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "notes": []
        }
        
        self.project_data.create_project(project_id, project_info)
        
        embed = discord.Embed(
            title="✅ Project Created Successfully!",
            description=f"**{project_info['name']}** has been added to the project board.",
            color=discord.Color.green()
        )
        embed.add_field(name="Project ID", value=project_id, inline=True)
        embed.add_field(name="Status", value="Planning", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AddMaterialModal(Modal, title="Add Materials"):
    def __init__(self, project_data: ProjectData, project_id: str):
        super().__init__()
        self.project_data = project_data
        self.project_id = project_id
    
    materials = TextInput(
        label="Materials Needed",
        placeholder="Enter materials (one per line):\nStone: 1000\nWood Planks: 500\nGlass: 200",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        material_lines = str(self.materials).strip().split('\n')
        materials_list = []
        
        for line in material_lines:
            if line.strip():
                materials_list.append(line.strip())
        
        project = self.project_data.get_project(self.project_id)
        if project:
            project['materials'] = materials_list
            self.project_data.update_project(self.project_id, {"materials": materials_list})
            
            await interaction.response.send_message(
                f"✅ Materials updated for **{project['name']}**!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Project not found!", ephemeral=True)

class UpdateProgressModal(Modal, title="Update Project Progress"):
    def __init__(self, project_data: ProjectData, project_id: str):
        super().__init__()
        self.project_data = project_data
        self.project_id = project_id
    
    progress = TextInput(
        label="Progress Percentage (0-100)",
        placeholder="Enter progress as a number (e.g., 75)",
        max_length=3,
        required=True
    )
    
    status = TextInput(
        label="Status",
        placeholder="Planning, In Progress, On Hold, Completed",
        max_length=20,
        required=True
    )
    
    notes = TextInput(
        label="Progress Notes (Optional)",
        placeholder="What was accomplished? Any challenges?",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            progress_val = int(str(self.progress))
            if progress_val < 0 or progress_val > 100:
                await interaction.response.send_message("❌ Progress must be between 0 and 100!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Progress must be a number!", ephemeral=True)
            return
        
        project = self.project_data.get_project(self.project_id)
        if project:
            updates = {
                "progress": progress_val,
                "status": str(self.status)
            }
            
            # Add timestamp for status changes
            if str(self.status).lower() == "in progress" and not project.get("started_at"):
                updates["started_at"] = datetime.now().isoformat()
            elif str(self.status).lower() == "completed" and not project.get("completed_at"):
                updates["completed_at"] = datetime.now().isoformat()
                updates["progress"] = 100
            
            # Add notes if provided
            if self.notes:
                if "notes" not in project:
                    project["notes"] = []
                project["notes"].append({
                    "timestamp": datetime.now().isoformat(),
                    "user": interaction.user.display_name,
                    "note": str(self.notes)
                })
                updates["notes"] = project["notes"]
            
            self.project_data.update_project(self.project_id, updates)
            
            await interaction.response.send_message(
                f"✅ Progress updated for **{project['name']}**! ({progress_val}% - {self.status})",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Project not found!", ephemeral=True)

class CollaboratorModal(Modal, title="Add Collaborator"):
    def __init__(self, project_data: ProjectData, project_id: str):
        super().__init__()
        self.project_data = project_data
        self.project_id = project_id
    
    username = TextInput(
        label="Minecraft Username",
        placeholder="Enter the username to add as collaborator",
        max_length=50,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        project = self.project_data.get_project(self.project_id)
        if project:
            username = str(self.username).strip()
            if username not in project.get("collaborators", []):
                if "collaborators" not in project:
                    project["collaborators"] = []
                project["collaborators"].append(username)
                self.project_data.update_project(self.project_id, {"collaborators": project["collaborators"]})
                
                await interaction.response.send_message(
                    f"✅ Added **{username}** as collaborator on **{project['name']}**!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ **{username}** is already a collaborator on this project!",
                    ephemeral=True
                )
        else:
            await interaction.response.send_message("❌ Project not found!", ephemeral=True)

class ProjectDetailView(View):
    def __init__(self, project_data: ProjectData, project_id: str):
        super().__init__(timeout=300)
        self.project_data = project_data
        self.project_id = project_id
    
    @discord.ui.button(label="📝 Update Progress", style=discord.ButtonStyle.primary)
    async def update_progress(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UpdateProgressModal(self.project_data, self.project_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🧱 Add Materials", style=discord.ButtonStyle.secondary)
    async def add_materials(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddMaterialModal(self.project_data, self.project_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="👥 Add Collaborator", style=discord.ButtonStyle.secondary)
    async def add_collaborator(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CollaboratorModal(self.project_data, self.project_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Delete Project", style=discord.ButtonStyle.danger)
    async def delete_project(self, interaction: discord.Interaction, button: discord.ui.Button):
        project = self.project_data.get_project(self.project_id)
        if project:
            # Only creator can delete
            if interaction.user.id != project.get("creator_id"):
                await interaction.response.send_message("❌ Only the project creator can delete this project!", ephemeral=True)
                return
            
            self.project_data.delete_project(self.project_id)
            await interaction.response.send_message(f"🗑️ Project **{project['name']}** has been deleted!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Project not found!", ephemeral=True)

class ProjectBoardView(View):
    def __init__(self, project_data: ProjectData):
        super().__init__(timeout=None)
        self.project_data = project_data
        self.update_project_buttons()
    
    def update_project_buttons(self):
        # Clear existing buttons except create new
        self.clear_items()
        
        # Add create new button
        create_button = Button(
            label="➕ Create New Project",
            style=discord.ButtonStyle.success,
            custom_id="create_project"
        )
        create_button.callback = self.create_project
        self.add_item(create_button)
        
        # Add refresh button
        refresh_button = Button(
            label="🔄 Refresh Board",
            style=discord.ButtonStyle.secondary,
            custom_id="refresh_board"
        )
        refresh_button.callback = self.refresh_board
        self.add_item(refresh_button)
        
        # Add project buttons (limit to 23 to leave room for create/refresh)
        projects = list(self.project_data.get_all_projects().items())[:21]
        for project_id, project in projects:
            # Status emoji
            status_emoji = {
                "Planning": "📋",
                "In Progress": "⚡",
                "On Hold": "⏸️",
                "Completed": "✅"
            }.get(project.get("status", "Planning"), "📋")
            
            button = Button(
                label=f"{status_emoji} {project['name'][:30]}",
                style=discord.ButtonStyle.primary,
                custom_id=f"project_{project_id}"
            )
            button.callback = lambda i, pid=project_id: self.view_project(i, pid)
            self.add_item(button)
    
    async def create_project(self, interaction: discord.Interaction):
        modal = CreateProjectModal(self.project_data)
        await interaction.response.send_modal(modal)
    
    async def refresh_board(self, interaction: discord.Interaction):
        self.update_project_buttons()
        embed = self.create_board_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def view_project(self, interaction: discord.Interaction, project_id: str):
        project = self.project_data.get_project(project_id)
        if not project:
            await interaction.response.send_message("❌ Project not found!", ephemeral=True)
            return
        
        embed = self.create_project_detail_embed(project)
        view = ProjectDetailView(self.project_data, project_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    def create_board_embed(self) -> discord.Embed:
        projects = self.project_data.get_all_projects()

        embed = discord.Embed(
            title="🗂️ Minecraft Project Board",
            description="Organized by progress level. Click buttons below to manage.",
            color=discord.Color.blurple()
        )

        if not projects:
            embed.add_field(
                name="No Projects Yet",
                value="Click '➕ Create New Project' to get started!",
                inline=False
            )
            return embed

        # Sort into progress tiers
        green = []
        orange = []
        red = []
        completed = []

        for pid, project in projects.items():
            name = project.get("name", "Unnamed")
            creator = project.get("creator", "Unknown")
            progress = int(project.get("progress", 0))
            status = project.get("status", "Planning")

            emoji = {
                "Planning": "📝",
                "In Progress": "🚧",
                "Completed": "✅",
                "On Hold": "⏸️"
            }.get(status, "📋")

            # Progress bar
            filled = "█" * (progress // 10)
            empty = "░" * (10 - (progress // 10))
            bar = f"`[{filled}{empty}]` {progress}%"

            value = (
                f"👤 **{creator}**\n"
                f"📊 **{status}**\n"
                f"{bar}"
            )

            field = (f"{emoji} {name}", value)

            if progress == 100:
                completed.append(field)
            elif progress >= 75:
                red.append(field)
            elif progress >= 50:
                orange.append(field)
            else:
                green.append(field)

        def add_project_rows(projects_list: List[tuple], label: str):
            if projects_list:
                # Add section header
                embed.add_field(name=f"__{label}__", value="\u200b", inline=False)

                # Add each project card (always inline=True)
                for title, content in projects_list:
                    embed.add_field(name=title, value=content, inline=True)

                # ✅ Pad last row if needed (to keep rows aligned)
                remainder = len(projects_list) % 3
                if remainder != 0:
                    for _ in range(3 - remainder):
                        embed.add_field(name="\u200b", value="\u200b", inline=True)

                # Optional: add spacing after section
                embed.add_field(name="\u200b", value="\u200b", inline=False)

        add_project_rows(green, "🟢 Low Progress (<50%)")
        add_project_rows(orange, "🟠 Medium Progress (50–74%)")
        add_project_rows(red, "🔴 High Priority (75–99%)")

        # Completed section (not inline, to give it full width)
        if completed:
            embed.add_field(name="__⬛ Completed Projects__", value="\u200b", inline=False)
            for name, val in completed:
                embed.add_field(name=name, value=val, inline=False)

        embed.set_footer(text=f"Total Projects: {len(projects)} • Use buttons below to manage.")
        return embed
    
    def create_project_detail_embed(self, project: Dict) -> discord.Embed:
        status_colors = {
            "Planning": discord.Color.orange(),
            "In Progress": discord.Color.blue(),
            "On Hold": discord.Color.yellow(),
            "Completed": discord.Color.green()
        }
        
        embed = discord.Embed(
            title=f"🏗️ {project['name']}",
            description=project['description'],
            color=status_colors.get(project.get('status', 'Planning'), discord.Color.blue())
        )
        
        # Basic info
        embed.add_field(name="📊 Status", value=project.get('status', 'Planning'), inline=True)
        embed.add_field(name="📈 Progress", value=f"{project.get('progress', 0)}%", inline=True)
        embed.add_field(name="👤 Creator", value=project.get('creator', 'Unknown'), inline=True)
        
        # Details
        embed.add_field(name="📏 Dimensions", value=project.get('dimensions', 'Not specified'), inline=True)
        embed.add_field(name="📍 Coordinates", value=project.get('coordinates', 'Not specified'), inline=True)
        embed.add_field(name="⏰ Estimated Time", value=project.get('estimated_time', 'Not specified'), inline=True)
        
        # Collaborators
        collaborators = project.get('collaborators', [])
        if collaborators:
            embed.add_field(
                name="👥 Collaborators",
                value=", ".join(collaborators),
                inline=False
            )
        
        # Materials
        materials = project.get('materials', [])
        if materials:
            materials_text = "\n".join(f"• {material}" for material in materials[:10])
            if len(materials) > 10:
                materials_text += f"\n... and {len(materials) - 10} more"
            embed.add_field(name="🧱 Materials Needed", value=materials_text, inline=False)
        
        # Recent notes
        notes = project.get('notes', [])
        if notes:
            recent_notes = notes[-3:]  # Last 3 notes
            notes_text = ""
            for note in recent_notes:
                timestamp = datetime.fromisoformat(note['timestamp']).strftime('%m/%d %H:%M')
                notes_text += f"**{timestamp}** - {note['user']}: {note['note']}\n"
            embed.add_field(name="📝 Recent Notes", value=notes_text, inline=False)
        
        # Timestamps
        created_at = datetime.fromisoformat(project['created_at']).strftime('%Y-%m-%d %H:%M')
        embed.set_footer(text=f"Project ID: {project['id']} | Created: {created_at}")
        
        return embed

class ProjectBoard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.project_data = ProjectData()
    
    @commands.command(name="projects")
    async def show_project_board(self, ctx):
        """Display the interactive project board"""
        view = ProjectBoardView(self.project_data)
        embed = view.create_board_embed()
        await ctx.send(embed=embed, view=view)
    
    @commands.command(name="myprojects")
    async def my_projects(self, ctx):
        """Show projects created by the user"""
        user_projects = {
            pid: project for pid, project in self.project_data.get_all_projects().items()
            if project.get('creator_id') == ctx.author.id
        }
        
        if not user_projects:
            await ctx.send("🔍 You haven't created any projects yet! Use `!projects` to create one.")
            return
        
        embed = discord.Embed(
            title=f"📋 {ctx.author.display_name}'s Projects",
            color=discord.Color.blue()
        )
        
        for project_id, project in user_projects.items():
            status_emoji = {
                "Planning": "📋",
                "In Progress": "⚡",
                "On Hold": "⏸️",
                "Completed": "✅"
            }.get(project.get("status", "Planning"), "📋")
            
            embed.add_field(
                name=f"{status_emoji} {project['name']}",
                value=f"Status: {project.get('status', 'Planning')}\nProgress: {project.get('progress', 0)}%",
                inline=True
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ProjectBoard(bot))