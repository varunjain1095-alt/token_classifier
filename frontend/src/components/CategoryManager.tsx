import React, { useState, useEffect } from 'react'

interface Category {
  id: string
  name: string
  type: 'primary' | 'secondary' | 'custom'
  description?: string
  position?: number
}

interface CategorySet {
  id: string
  name: string
  description: string
  categories: Category[]
  version: number
  is_active: boolean
}

interface CategoryManagerProps {
  onCategorySetSelect: (categorySet: CategorySet) => void
}

const CategoryManager: React.FC<CategoryManagerProps> = ({ onCategorySetSelect }) => {
  const [categorySets, setCategorySets] = useState<CategorySet[]>([])
  const [selectedSet, setSelectedSet] = useState<CategorySet | null>(null)
  const [showCreateForm, setShowCreateForm] = useState<boolean>(false)
  const [newSetName, setNewSetName] = useState<string>('')
  const [newSetDescription, setNewSetDescription] = useState<string>('')
  const [categories, setCategories] = useState<Category[]>([
    { id: '550e8400-e29b-41d4-a716-446655440001', name: 'Positive', type: 'primary', position: 0 },
    { id: '550e8400-e29b-41d4-a716-446655440002', name: 'Negative', type: 'primary', position: 1 },
    { id: '550e8400-e29b-41d4-a716-446655440003', name: 'Neutral', type: 'primary', position: 2 }
  ])

  useEffect(() => {
    loadCategorySets()
  }, [])

  const loadCategorySets = async () => {
    try {
      const response = await fetch('/api/configuration/category-sets')
      const data = await response.json()
      if (data.success) {
        setCategorySets(data.category_sets)
      }
    } catch (error) {
      console.error('Failed to load category sets:', error)
    }
  }

  const createCategorySet = async () => {
    try {
      const response = await fetch('/api/configuration/category-sets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: newSetName,
          description: newSetDescription,
          categories: categories
        }),
      })
      
      const data = await response.json()
      if (data.success) {
        setShowCreateForm(false)
        setNewSetName('')
        setNewSetDescription('')
        loadCategorySets()
      } else {
        alert('Failed to create category set: ' + data.error)
      }
    } catch (error) {
      alert('Error creating category set: ' + error)
    }
  }

  const addCategory = () => {
    const newCategory: Category = {
      id: `550e8400-e29b-41d4-a716-44665544000${categories.length + 4}`,
      name: '',
      type: 'custom',
      position: categories.length
    }
    setCategories([...categories, newCategory])
  }

  const updateCategory = (index: number, field: keyof Category, value: string) => {
    const updatedCategories = [...categories]
    updatedCategories[index] = { ...updatedCategories[index], [field]: value }
    setCategories(updatedCategories)
  }

  const removeCategory = (index: number) => {
    const updatedCategories = categories.filter((_, i) => i !== index)
    setCategories(updatedCategories)
  }

  const selectCategorySet = (categorySet: CategorySet) => {
    setSelectedSet(categorySet)
    onCategorySetSelect(categorySet)
  }

  const getTypeColor = (type: string) => {
    const colors = {
      'primary': 'var(--info-soft)',
      'secondary': 'var(--primary-soft)',
      'custom': 'var(--success-soft)'
    }
    return colors[type as keyof typeof colors] || 'var(--surface-2)'
  }

  return (
    <div style={{ margin: '20px 0' }}>
      <h3>Category Management</h3>
      
      {/* Category Sets List */}
      <div style={{ marginBottom: '30px' }}>
        <h4>Category Sets</h4>
        {categorySets.length === 0 ? (
          <p>No category sets found. Create your first category set below.</p>
        ) : (
          <div style={{ display: 'grid', gap: '10px' }}>
            {categorySets.map((set) => (
              <div
                key={set.id}
                onClick={() => selectCategorySet(set)}
                style={{
                  padding: '15px',
                  border: selectedSet?.id === set.id ? '2px solid var(--primary)' : '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  backgroundColor: selectedSet?.id === set.id ? 'var(--info-soft)' : 'var(--surface-2)'
                }}
              >
                <div style={{ fontWeight: 'bold' }}>{set.name}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-2)' }}>
                  Version {set.version} • {set.categories.length} categories
                </div>
                {set.description && (
                  <div style={{ fontSize: '12px', marginTop: '5px' }}>{set.description}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create New Category Set */}
      <div style={{ marginBottom: '30px' }}>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          style={{
            padding: '10px 20px',
            backgroundColor: 'var(--success)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer',
            marginBottom: '15px'
          }}
        >
          {showCreateForm ? 'Cancel' : 'Create New Category Set'}
        </button>

        {showCreateForm && (
          <div style={{
            padding: '20px',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--surface-2)'
          }}>
            <h4>Create Category Set</h4>
            
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                Name:
              </label>
              <input
                type="text"
                value={newSetName}
                onChange={(e) => setNewSetName(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)'
                }}
                placeholder="e.g., Sentiment Categories"
              />
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                Description:
              </label>
              <textarea
                value={newSetDescription}
                onChange={(e) => setNewSetDescription(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  height: '60px'
                }}
                placeholder="Optional description..."
              />
            </div>

            {/* Categories */}
            <div style={{ marginBottom: '15px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <label style={{ fontWeight: 'bold' }}>Categories:</label>
                <button
                  onClick={addCategory}
                  style={{
                    padding: '5px 10px',
                    backgroundColor: 'var(--primary)',
                    color: 'white',
                    border: 'none',
                    borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer',
                    fontSize: '12px'
                  }}
                >
                  Add Category
                </button>
              </div>
              
              {categories.map((category, index) => (
                <div key={index} style={{
                  display: 'flex',
                  gap: '10px',
                  marginBottom: '10px',
                  padding: '10px',
                  backgroundColor: getTypeColor(category.type),
                  borderRadius: 'var(--radius-sm)',
                  alignItems: 'center'
                }}>
                  <input
                    type="text"
                    value={category.name}
                    onChange={(e) => updateCategory(index, 'name', e.target.value)}
                    placeholder="Category name"
                    style={{
                      flex: 1,
                      padding: '5px',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)'
                    }}
                  />
                  <select
                    value={category.type}
                    onChange={(e) => updateCategory(index, 'type', e.target.value as any)}
                    style={{
                      padding: '5px',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)'
                    }}
                  >
                    <option value="primary">Primary</option>
                    <option value="secondary">Secondary</option>
                    <option value="custom">Custom</option>
                  </select>
                  <input
                    type="number"
                    value={category.position || index}
                    onChange={(e) => updateCategory(index, 'position', e.target.value)}
                    placeholder="Position"
                    style={{
                      width: '60px',
                      padding: '5px',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)'
                    }}
                  />
                  <button
                    onClick={() => removeCategory(index)}
                    style={{
                      padding: '5px 10px',
                      backgroundColor: 'var(--danger)',
                      color: 'white',
                      border: 'none',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>

            <button
              onClick={createCategorySet}
              disabled={!newSetName.trim()}
              style={{
                padding: '10px 20px',
                backgroundColor: newSetName.trim() ? 'var(--success)' : 'var(--border)',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                cursor: newSetName.trim() ? 'pointer' : 'not-allowed'
              }}
            >
              Create Category Set
            </button>
          </div>
        )}
      </div>

      {/* Selected Category Set Details */}
      {selectedSet && (
        <div style={{
          padding: '20px',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          backgroundColor: 'var(--success-soft)'
        }}>
          <h4>Selected: {selectedSet.name}</h4>
          <p><strong>Version:</strong> {selectedSet.version}</p>
          {selectedSet.description && <p><strong>Description:</strong> {selectedSet.description}</p>}
          
          <h5>Categories ({selectedSet.categories.length}):</h5>
          <div style={{ display: 'grid', gap: '5px' }}>
            {selectedSet.categories
              .sort((a, b) => (a.position || 0) - (b.position || 0))
              .map((category, index) => (
                <div key={index} style={{
                  padding: '8px',
                  backgroundColor: getTypeColor(category.type),
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  justifyContent: 'space-between'
                }}>
                  <span>{category.name}</span>
                  <span style={{ fontSize: '12px', color: 'var(--text-2)' }}>
                    {category.type} • Position {category.position || index}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default CategoryManager
